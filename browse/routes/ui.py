"""Provides the user intefaces for browse."""
from typing import Union

from arxiv import status
from flask import Blueprint, render_template, request, Response, session, \
    redirect, current_app
from werkzeug.exceptions import InternalServerError, NotFound

from browse.controllers import abs_page, get_institution_from_request
from browse.util.clickthrough import is_hash_valid

blueprint = Blueprint('browse', __name__, url_prefix='')


@blueprint.before_request
def before_request() -> None:
    """Get instituional affiliation from session."""
    if 'institution' not in session:
        institution = get_institution_from_request()
        session['institution'] = institution


@blueprint.after_request
def apply_response_headers(response: Response) -> Response:
    """Prevent UI redress attacks."""
    """Hook for applying response headers to all responses."""
    response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response


@blueprint.route('/abs', methods=['GET'])
def bare_abs():
    """Return 404."""
    raise NotFound


@blueprint.route('/abs/', methods=['GET'], defaults={'arxiv_id': ''})
@blueprint.route('/abs/<path:arxiv_id>', methods=['GET', 'POST'])
def abstract(arxiv_id: str) -> Union[str, Response]:
    """Abstract (abs) page view."""
    download_format_pref = request.cookies.get('xxx-ps-defaults')
    response, code, headers = abs_page.get_abs_page(arxiv_id,
                                                    request.args,
                                                    download_format_pref)

    if code == status.HTTP_200_OK:
        return render_template('abs/abs.html', **response), code, headers
    elif code == status.HTTP_301_MOVED_PERMANENTLY:
        return redirect(headers['Location'], code=code)

    raise InternalServerError('Unexpected error')


@blueprint.route('/trackback/', methods=['GET'], defaults={'arxiv_id': ''})
@blueprint.route('/trackback/<path:arxiv_id>', methods=['GET', 'POST'])
def trackback(arxiv_id: str) -> Union[str, Response]:
    """Route to define new trackbacks for papers."""
    # TODO implement
    raise NotFound


@blueprint.route('/ct')
def clickthrough():
    """Controller to log clickthrough to bookmarking sites."""
    if 'url' in request.args and 'v' in request.args \
            and is_hash_valid(current_app.config['SECRET_KEY'], request.args.get('url'), request.args.get('v')):
        return redirect(request.args.get('url'))
    else:
        raise NotFound()

# Satic resources (not sure how to do these in NG):
# @blueprint.route(//static.arxiv.org/css/arXiv.css?v=20170424)
# @blueprint.route(/favicon.ico)
# @blueprint.route(http://arxiv.org/)

# Not sure how to do these cross repo links,
# Will talk to Erick or look into arxiv-base to see.
# @blueprint.route(/IgnoreMe)
# @blueprint.route(/find)
# @blueprint.route(/form)
# @blueprint.route(/help)
# @blueprint.route(/help/arxiv_identifier)
# @blueprint.route(/help/arxiv_identifier)
# @blueprint.route(/help/mathjax/)
# @blueprint.route(/help/trackback/)
# @blueprint.route(/help/contact)
# @blueprint.route(/help/social_bookmarking)
# @blueprint.route(/search)
# @blueprint.route(/user/login)


@blueprint.route('/list/<context>/<subcontext>')
def list_articles(current_context: str, yymm: str):
    # context might be a context or an archive
    # subcontext should be 'recent' 'new' or a string of format yymm
    raise InternalServerError('Not yet implemented')


@blueprint.route('/format/<arxiv_id>')
def format(arxiv_id: str):
    raise InternalServerError('Not yet implemented')


@blueprint.route('/pdf/<arxiv_id>')
def pdf(arxiv_id: str):
    raise InternalServerError('Not yet implemented')


@blueprint.route('/div/<arxiv_id>')
def div(arxiv_id: str):
    raise InternalServerError('Not yet implemented')


@blueprint.route('/html/<arxiv_id>')
def html(arxiv_id: str):
    raise InternalServerError('Not yet implemented')


@blueprint.route('/ps/<arxiv_id>')
def ps(arxiv_id: str):
    raise InternalServerError('Not yet implemented')


@blueprint.route('/src/<arxiv_id>/anc', defaults={'file_name': None})
@blueprint.route('/src/<arxiv_id>/anc/<path:file_name>')
def src(arxiv_id: str, file_name: str):
    raise InternalServerError('Not Yet Implemented')


@blueprint.route('/tb/<path:arxiv_id>')
def tb(arxiv_id: str):
    raise InternalServerError('Not yet implemented')


@blueprint.route('/show-email/<path:show_email_hash>/<path:arxiv_id>')
def show_email(show_email_hash: str, arxiv_id: str):
    raise InternalServerError('Not Yet Implemented')


# Maybe auth protected URL in arxiv-browse? ('will the auth service allow paths not defined in it's repo to be protected?')
@blueprint.route('/auth/show-endorsers/<path:arxiv_id>')
def show_endorsers(arxiv_id: str):
    raise InternalServerError('Not yet implemented')


@blueprint.route('/refs/<path:arxiv_id>')
def refs(arxiv_id: str):
    raise InternalServerError('Not yet implemented')


@blueprint.route('/cits/<path:arxiv_id>')
def cits(arxiv_id: str):
    raise InternalServerError('Not yet implemented')


@blueprint.route('/form')
def form(arxiv_id: str):
    raise InternalServerError('Not yet implemented')
