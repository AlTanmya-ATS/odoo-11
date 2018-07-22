# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class MasEntriesWizard(models.TransientModel):
    _name='asset_management.mas_entries_wizard'
    date_from=fields.Date(required=True)
    date_to = fields.Date(required=True,)
    post_entries=fields.Boolean()
    book_id = fields.Many2one('asset_management.book', required=True,
                              domain=[('active', '=', True)])

    @api.constrains('date_from', 'date_to')
    def _check_dates_of_entries(self):
        if self.date_to < self.date_from:
            raise ValidationError("Ending Date cannot be set before starting Date. ")

    @api.multi
    def moves_compute(self):
        asset_move_ids=self.env['asset_management.asset'].generate_mas_entries(self.date_from,self.date_to,self.post_entries,self.book_id.id)
        if self.post_entries is True:
            for record in asset_move_ids:
                record.move_id.post()

        moved_lines=[]
        for record in asset_move_ids:
            moved_lines.append(record.move_id.id)

        return {
            'name':_('Created Assets Move'),
            'res_model':'account.move',
            'view_type':'form',
            'view_mode':'tree,form',
            'view_id':False,
            'type': 'ir.actions.act_window',
            'domain':[('id','in',moved_lines)],
        }