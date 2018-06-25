from odoo import fields,api,models,_

class ModifyDep(models.TransientModel):
    _name='asset_management.modify_dep'
    name = fields.Char()
    asset_id=fields.Many2one('asset_management.asset')
    book_id=fields.Many2one('asset_management.book',domain=[('active','=',True)])
    dep_method=fields.Selection([('linear','Linear'),('degressive','Degressive')],string='Deprecation Method')
    life_months=fields.Integer()
    method_number=fields.Integer()
    method_progress_factor=fields.Float()
    method_time=fields.Selection([('end','End Date'),('number','Number of entries')])
    end_date=fields.Date()

    @api.onchange('book_id')
    def _asset_in_book_domain(self):
        if self.book_id:
            res=[]
            assets_in_book=self.env['asset_management.book_assets'].search([('book_id','=',self.book_id.id),('depreciated_flag','=',True)])
            for asset in assets_in_book:
                res.append(asset.asset_id.id)

            return {'domain':{'asset_id':[('id','in',res)]
                              }}

    @api.onchange('book_id','asset_id')
    def get_record_values(self):
        vals = self.onchange_book_id_value(self.book_id.id,self.asset_id.id)
        # We cannot use 'write' on an object that doesn't exist yet
        if vals:
            for k, v in vals['value'].items():
                setattr(self, k, v)

    def onchange_book_assets_id_value(self, book_id,asset_id):
        if book_id and asset_id:
            asset = self.env['asset_management.book_assets'].search(
                [('book_id', '=', self.book_id.id), ('asset_id', '=', self.asset_id.id)])
            return {
                'value': {
                    'dep_method': asset.method,
                    'life_months': asset.life_months,
                    'method_progress_factor': asset.method_progress_factor,
                    'method_time': asset.method_time,
                    'method_number': asset.method_number,
                    'end_date': asset.end_date,
                }
            }


    @api.multi
    def modify(self):
        asset = self.env['asset_management.book_assets'].search([('asset_id','=',self.asset_id.id),('book_id','=',self.book_id.id)])
        new_values={
            'method':self.dep_method,
            'life_months':self.life_months,
            'method_progress_factor':self.method_progress_factor,
            'method_time':self.method_time,
            'method_number':self.method_number,
            'end_date':self.end_date
        }
        asset.write(new_values)
        asset.compute_depreciation_board()
        return {'type':'ir.actions.act_window_close'}
