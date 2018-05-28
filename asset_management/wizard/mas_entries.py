# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class MasEntriesWizard(models.TransientModel):
    _name='asset_management.mas_entries_wizard'
    date = fields.Date(string="Date", required=True,)
    post_entries=fields.Boolean()


    @api.multi
    def moves_compute(self):
        asset_move_ids=self.env['asset_management.asset'].generate_mas_entries(self.date)
        if self.post_entries is True:
            for record in asset_move_ids:
                record.move_id.post()

        return {
            'name':_('Created Assets Move'),
            'model':'account.move',
            'view_type':'form',
            'view_mode':'tree,form',
            'view_id':False,
            'type': 'ir.actions.act_window',
            'domain':[('id','in',asset_move_ids)],
            'target':'current'
        }
