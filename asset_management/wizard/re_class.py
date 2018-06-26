# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class ReClass(models.TransientModel):
    _name='asset_management.re_class_wizard'
    asset_id=fields.Many2one('asset_management.asset')
    book_id=fields.Many2one('asset_management.book',domain=[('active','=',True)])
    category_id=fields.Many2one('asset_management.category',compute="_get_book_category")
    new_category_id=fields.Many2one('asset_management.category')

    @api.onchange('book_id')
    def _onchange_book_id(self):
        if self.book_id:
            assets = []
            asset_in_book = self.env['asset_management.book_assets'].search(
                [('asset_id', '=', self.book_id.id), ('state', '=', 'open')])
            for record in asset_in_book:
                assets.append(record.book_id.id)

            return {'domain': {'asset_id': [('id', 'in', assets)]
                               }}

    @api.onchange('asset_id')
    def _onchange_asset_id(self):
        if self.asset_id:
            categorys = []
            category_books = self.env['asset_management.category_books'].search([('book_id', '=', self.book_id.id)])
            for record in category_books:
                if record.category_id.active and record.category_id.id != self.category_id.id:
                    categorys.append(record.category_id.id)

            return {'domain': {'new_category_id': [('id', 'in', categorys)]
                               }}

    @api.depends('book_id','asset_id')
    def _get_book_category(self):
        category_of_book=self.env['asset_management.book_assets'].search([('book_id','=',self.book_id.id),('asset_id','=',self.asset_id.id)])
        self.category_id=category_of_book.category_id.id


    @api.multi
    def asset_re_class(self):
        new_category=self.env['asset_management.book_assets'].search([('asset_id','=',self.asset_id.id),('book_id','=',self.book_id.id)])
        new_depreciation_expense_account=self.env['asset_management.category_books'].search([('category_id','=',self.new_category_id.id),
                                                                                             ('book_id','=',self.book_id.id)]).depreciation_expense_account
        new_values={
        'category_id':self.new_category_id.id
        }
        new_category.write(new_values)
        for assignment in new_category.assignment_id:
            assignment.depreciation_expense_account=new_depreciation_expense_account.id
        return {'type':'ir.actions.act_window_close'}
