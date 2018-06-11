# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.fields import Date as fDate
from datetime import timedelta


class LibraryBook(models.Model):
_name = 'library.book'
_inherit = ['base.archive']
_description = 'Library Book'
_order = 'date_release desc, name'
_rec_name = 'short_name'
name = fields.Char('Title', required=True)
short_name = fields.Char('Short Title', required=True)
date_release = fields.Date('Release Date')
author_ids = fields.Many2many('res.partner', string='Authors')
publisher_id = fields.Many2one('res.partner', string='Publisher')
publisher_city = fields.Char(
'Publisher City',
related='publisher_id.city',
readonly=True)
_sql_constraints = [
('name_uniq',
'UNIQUE (name)',
'Book title must be unique.')
]
@api.constrains('date_release')
def _check_release_date(self):
for record in self:
if (record.date_release and
record.date_release > fields.Date.today()):
raise models.ValidationError(
'Release date must be in the past')
age_days = fields.Float(
string='Days Since Release',
compute='_compute_age',
inverse='_inverse_age',
search='_search_age',
store=False,
compute_sudo=False,
)
@api.depends('date_release')
def _compute_age(self):
today = fDate.from_string(fDate.today())
for book in self.filtered('date_release'):
delta = (today -
fDate.from_string(book.date_release))
book.age_days = delta.days

def _inverse_age(self):
today = fDate.from_string(fDate.context_today(self))
for book in self.filtered('date_release'):
d = today - timedelta(days=book.age_days)
book.date_release = fDate.to_string(d)

def _search_age(self, operator, value):
today = fDate.from_string(fDate.context_today(self))
value_days = timedelta(days=value)
value_date = fDate.to_string(today - value_days)
# convert the operator:
# book with age > value have a date < value_date
operator_map = {
'>': '<', '>=': '<=',
'<': '>', '<=': '>=',
}
new_op = operator_map.get(operator, operator)
return [('date_release', new_op, value_date)]



class BaseArchive(models.AbstractModel):
_name = 'base.archive'
active = fields.Boolean(default=True)
def do_archive(self):
for record in self:
record.active = not record.active



class ResPartner(models.Model):
_inherit = 'res.partner'
published_book_ids = fields.One2many(
'library.book', 'publisher_id',
string='Published Books')
authored_book_ids = fields.Many2many(
'library.book',
string='Authored Books')
count_books = fields.Integer(
'Number of Authored Books',
compute='_compute_count_books'
)
@api.depends('authored_book_ids')
def _compute_count_books(self):
for r in self:
r.count_books = len(r.authored_book_ids)


class LibraryMember(models.Model):
_name = 'library.member'
_inherits = {'res.partner': 'partner_id'}
partner_id = fields.Many2one(
'res.partner',
ondelete='cascade')
date_start = fields.Date('Member Since')
date_end = fields.Date('Termination Date')
member_number = fields.Char()
date_of_birth = fields.Date('Date of birth')


# class mozapp01(models.Model):
#     _name = 'mozapp01.mozapp01'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         self.value2 = float(self.value) / 100