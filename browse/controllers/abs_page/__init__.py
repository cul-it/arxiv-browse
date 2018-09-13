"""
Handle requests to support the abs feature.

The primary entrypoint to this module is :func:`.get_abs_page`, which handles
GET requests to the abs endpoint.
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

from flask import current_app as app
from flask import url_for

from werkzeug.exceptions import InternalServerError
from werkzeug.datastructures import MultiDict

from arxiv import status, taxonomy
from arxiv.base import logging
from browse.domain.metadata import DocMetadata
from browse.exceptions import AbsNotFound
from browse.services.search.search_authors import queries_for_authors, \
    split_long_author_list
from browse.services.util.metatags import meta_tag_metadata
from browse.services.document import metadata
from browse.services.document.metadata import AbsException,\
    AbsNotFoundException, AbsVersionNotFoundException, AbsDeletedException
from browse.services.util.response_headers import mime_header_date
from browse.domain.identifier import Identifier, IdentifierException,\
    IdentifierIsArchiveException
from browse.services.database import count_trackback_pings,\
    get_trackback_ping_latest_date, has_sciencewise_ping, \
    get_dblp_listing_path, get_dblp_authors
from browse.services.util.external_refs_cits import include_inspire_link,\
    include_dblp_section, get_computed_dblp_listing_path, get_dblp_bibtex_path
from browse.services.document.config.external_refs_cits import DBLP_BASE_URL,\
    DBLP_BIBTEX_PATH, DBLP_AUTHOR_SEARCH_PATH

logger = logging.getLogger(__name__)

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]

truncate_author_list_size = 100


def get_abs_page(arxiv_id: str,
                 request_params: MultiDict,
                 download_format_pref: Optional[str] = None) -> Response:
    """
    Get abs page data from the document metadata service.

    Parameters
    ----------
    arxiv_id : str
        The arXiv identifier as provided in the request.
    request_params : dict
    download_format_pref: str
        Download format preference.

    Returns
    -------
    dict
        Search result response data.
    int
        HTTP status code.
    dict
        Headers to add to the response.

    Raises
    ------
    :class:`.InternalServerError`
        Raised when there was an unexpected problem executing the query.

    """
    response_data: Dict[str, Any] = {}
    response_headers: Dict[str, Any] = {}
    try:

        arxiv_id = _check_legacy_id_params(arxiv_id, request_params)

        arxiv_identifier = Identifier(arxiv_id=arxiv_id)
        redirect_url = _check_supplied_identifier(arxiv_identifier)
        if redirect_url:
            return {},\
                status.HTTP_301_MOVED_PERMANENTLY,\
                {'Location': redirect_url}

        abs_meta = metadata.get_abs(arxiv_id)
        response_data['abs_meta'] = abs_meta
        response_data['meta_tags'] = meta_tag_metadata(abs_meta)
        response_data['author_links'] = \
            split_long_author_list(queries_for_authors(
                abs_meta.authors.raw), truncate_author_list_size)
        response_data['url_for_author_search'] = \
            lambda author_query: url_for('search_archive',
                                         searchtype='author',
                                         archive=abs_meta.primary_archive.id,
                                         query=author_query)

        # Dissemination formats for download links
        add_sciencewise_ping = _check_sciencewise_ping(abs_meta.arxiv_id_v)
        response_data['formats'] = metadata.get_dissemination_formats(
            abs_meta,
            download_format_pref,
            add_sciencewise_ping)

        # Following are less critical and template must display without them
        try:
            response_data['include_inspire_link'] = include_inspire_link(
                abs_meta)
            response_data['dblp'] = _check_dblp(abs_meta)
            response_data['trackback_ping_count'] = count_trackback_pings(
                arxiv_id)
            if response_data['trackback_ping_count'] > 0:
                response_data['trackback_ping_latest'] = \
                    get_trackback_ping_latest_date(arxiv_id)

            # Ancillary files
            response_data['ancillary_files'] = \
                metadata.get_ancillary_files(abs_meta)

            # Browse context
            _check_context(arxiv_identifier,
                           request_params,
                           response_data)
        except Exception:
            logger.error("Error getting non-critical abs page data",
                         exc_info=app.debug)

    except AbsNotFoundException:
        if arxiv_identifier.is_old_id and arxiv_identifier.archive \
           in taxonomy.ARCHIVES:
            archive_name = taxonomy.ARCHIVES[arxiv_identifier.archive]['name']
            raise AbsNotFound(data={'reason': 'old_id_not_found',
                                    'arxiv_id': arxiv_id,
                                    'archive_id': arxiv_identifier.archive,
                                    'archive_name': archive_name})
        raise AbsNotFound(data={'reason': 'not_found', 'arxiv_id': arxiv_id})
    except AbsVersionNotFoundException:
        raise AbsNotFound(data={'reason': 'version_not_found',
                                'arxiv_id': arxiv_identifier.idv,
                                'arxiv_id_latest': arxiv_identifier.id})
    except AbsDeletedException as e:
        raise AbsNotFound(data={'reason': 'deleted',
                                'arxiv_id_latest': arxiv_identifier.id,
                                'message': e})
    except IdentifierIsArchiveException as e:
        raise AbsNotFound(data={'reason': 'is_archive',
                                'arxiv_id': arxiv_id,
                                'archive_name': e})
    except IdentifierException:
        raise AbsNotFound(data={'arxiv_id': arxiv_id})
    except AbsException as e:
        raise InternalServerError(
            'There was a problem. If this problem persists, please contact '
            'help@arxiv.org.') from e

    response_status = status.HTTP_200_OK

    if response_data['trackback_ping_latest'] \
       and abs_meta.modified \
       and response_data['trackback_ping_latest'] > abs_meta.modified:
        response_headers['Last-Modified'] = \
            mime_header_date(response_data['trackback_ping_latest'])
    elif abs_meta.modified:
        response_headers['Last-Modified'] = mime_header_date(abs_meta.modified)

    if response_headers['Last-Modified']:
        response_headers['ETag'] = response_headers['Last-Modified']

    return response_data, response_status, response_headers


def _check_supplied_identifier(arxiv_identifier: Identifier) -> Optional[str]:
    """
    Provide redirect URL if supplied ID does not match parsed ID.

    Parameters
    ----------
    arxiv_identifier : :class:`Identifier`

    Returns
    -------
    redirect_url: str
        A `browse.abstract` redirect URL that uses the canonical
        arXiv identifier.

    """
    if arxiv_identifier and arxiv_identifier.ids != arxiv_identifier.id and \
            arxiv_identifier.ids != arxiv_identifier.idv:
        redirect_url: str = url_for('browse.abstract',
                                    arxiv_id=arxiv_identifier.idv
                                    if arxiv_identifier.has_version
                                    else arxiv_identifier.id)
        return redirect_url
    return None


def _check_legacy_id_params(arxiv_id: str, request_params: MultiDict) -> str:
    """
    Check for legacy request parameters related to old arXiv identifiers.

    Parameters
    ----------
    arxiv_id : str

    request_params: MultiDict

    Returns
    -------
    arxiv_id: str
        A possibly modified version of the input arxiv_id string.

    """
    if request_params and '/' not in arxiv_id:
        # To support old references to /abs/<archive>?papernum=\d{7}
        if 'papernum' in request_params:
            return f"{arxiv_id}/{request_params['papernum']}"
        else:
            for param in request_params:
                # singleton case, where the parameter is the value
                # To support old references to /abs/<archive>?\d{7}
                if not request_params[param] \
                   and re.match(r'^\d{7}$', param):
                    return f'{arxiv_id}/{param}'
    return arxiv_id


def _check_context(arxiv_identifier: Identifier,
                   request_params: MultiDict,
                   response_data: Dict[str, Any]) -> None:
    """
    Check context in request parameters and update response accordingly.

    Parameters
    ----------
    arxiv_identifier : :class:`Identifier`

    request_params: MultiDict

    response_data: dict

    Returns
    -------
    None

    """
    if 'context' in request_params\
       and (request_params['context'] in taxonomy.CATEGORIES
            or request_params['context'] in taxonomy.ARCHIVES
            or request_params['context'] == 'arxiv'):
        if request_params['context'] == 'arxiv':
            response_data['browse_context_next_id'] = \
                metadata.get_next_id(arxiv_identifier)
            response_data['browse_context_previous_id'] = \
                metadata.get_previous_id(arxiv_identifier)
        response_data['browse_context'] = request_params['context']
    elif arxiv_identifier.is_old_id:
        response_data['browse_context_next_id'] = \
            metadata.get_next_id(arxiv_identifier)
        response_data['browse_context_previous_id'] = \
            metadata.get_previous_id(arxiv_identifier)


def _check_sciencewise_ping(paper_id_v: str) -> bool:
    """Check whether paper has a ScienceWISE ping."""
    try:
        return has_sciencewise_ping(paper_id_v)
    except IOError:
        return False


def _check_dblp(docmeta: DocMetadata,
                db_override: bool = False) -> Optional[Dict]:
    """Check whether paper has DBLP Bibliography entry."""
    if not include_dblp_section(docmeta):
        return None
    identifier = docmeta.arxiv_identifier
    listing_path = None
    author_list: List[str] = []
    # fallback check in case DB service is not available
    if db_override:
        listing_path = get_computed_dblp_listing_path(docmeta)
    else:
        try:
            if identifier.id is None:
                return None
            listing_path = get_dblp_listing_path(identifier.id)
            if not listing_path:
                return None
            author_list = get_dblp_authors(identifier.id)
        except IOError:
            # log this
            return None
    if listing_path is not None:
        bibtex_path = get_dblp_bibtex_path(listing_path)
    else:
        return None
    return {
        'base_url': DBLP_BASE_URL,
        'author_search_url':
            urljoin(DBLP_BASE_URL, DBLP_AUTHOR_SEARCH_PATH),
        'bibtex_base_url': urljoin(DBLP_BASE_URL, DBLP_BIBTEX_PATH),
        'bibtex_path': bibtex_path,
        'listing_url': urljoin(DBLP_BASE_URL, listing_path),
        'author_list': author_list
    }
