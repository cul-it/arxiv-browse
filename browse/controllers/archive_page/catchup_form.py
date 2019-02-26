"""Form for Catchup."""
from typing import List, Any, Dict

from flask_wtf import FlaskForm
from wtforms import SelectField, HiddenField, SubmitField
from wtforms.validators import DataRequired

MONTHS = [
    ("01", "01 (Jan)"),
    ("02", "02 (Feb)"),
    ("03", "03 (Mar)"),
    ("04", "04 (Apr)"),
    ("05", "05 (May)"),
    ("06", "06 (Jun)"),
    ("07", "07 (Jul)"),
    ("08", "08 (Aug)"),
    ("09", "09 (Sep)"),
    ("10", "10 (Oct)"),
    ("11", "11 (Nov)"),
    ("12", "12 (Dec)"),
]

DAYS = [(str(i), "{:0>2d}".format(i)) for i in range(1, 32)]


class CatchupForm(FlaskForm):
    """Form for catchup.

    This doesn't try to account for the start date of the 
    archive, end date of the archive or dates in the future. 
    It just accepts these, and expects the /list controller
    to deal with dates for which there are no articles.
    """

    day = SelectField("sday", validators=[DataRequired()], choices=DAYS)

    month = SelectField("smonth", validators=[DataRequired()], choices=MONTHS)

    year = SelectField("syear", validators=[DataRequired()] )

    abstracts = SelectField(
        "method", choices=[("without", "without"), ("with", "with")]
    )
    archive = HiddenField("archive", validators=[DataRequired()])
    submit = SubmitField("Go")

    def __init__(self, archive_id: str, archive: Dict[str, Any], years: List[int]):
        super(CatchupForm, self).__init__()
        self.year.choices = [(str(yer)[-2:], str(yer)) for yer in years]
        self.archive.data = archive_id
        # self.years = years
        # TODO how many years are we suppose to show on the catchupform?
        # TODO set selected month to now.month - 1
        # TODO set day to now.dayOfMonth - 7 days ago
