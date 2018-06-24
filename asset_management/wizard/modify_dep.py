from odoo import fields,api,models,_

class ModifyDep(models.TransientModel):
    _name='asset_management.modify_dep'
    name = fields.Char()
    asset_id=fields.Many2one('asset_management.asset')
    book_id=fields.Many2one('asset_management.book_id',domain=[('active','=',True)])
    dep_method=fields.Selection([('linear','Linear'),('degressive','Degressive')],string='Deprecation Method')
    life_months=fields.Integer()
    method_number=fields.Integer()
    method_progress_factor=fields.Float()
    method_time=fields.Selection([('end','End Date'),('number','Number of entries')])

    @api.onchange('book_id')
    def _asset_in_book_domain(self):
        if self.book_id:
            res=[]
            assets_in_book=self.env['asset_management.book_assets'].search([('book_id','=',self.book_id.id),('depreciated_flag','=',True)])
            for asset in assets_in_book:
                res.append(asset.asset_id.id)

            return {'domain':{'asset_id':[('id','in',res)]
                              }}

    @api.model
    def default_get(self,fields):
        res=super(ModifyDep, self).default_get(fields)
        asset=self.env['asset_management.book_assets'].browse([('book_id','=',self.book_id.id),('asset_id','=',self.asset_id.id)])
        if 'method' in fields:
            res.update({'dep_method':asset.method})
        if 'life_months' in fields:
            res.update({'life_months':asset.life_months})
        if 'method_progress_factor' in fields and asset.dep_method == 'degressive':
            res.update({'method_progress_factor':asset.method_progress_factor})
        if 'method_time' in fields:
            res.update({'method_time':asset.method_time})
        if 'method_number' in fields and asset.method_time == 'number':
            res.update({'method_number':asset.method_number})
        if 'end_date' in fields and asset.method_time == 'end':
            res.update({'end_date':asset.end_date})

        return res

    @api.multi
    def modify(self):
        asset = self.env['asset_management.book_assets'].search([('asset_id','=',self.asset_id.id),('book_id','=',self.book_id.id)])
        new_values={
            'method':self.dep_method,
            'life_months':self.life_months,
            'method_progress_factor':self.method_progress_factore,
            'method_time':self.method_time,
            'method_number':self.method_number,
            'end_date':self.end_date
        }
        asset.write(new_values)
        asset.compute_depreciation_board()
        return {'type':'ir.actions.act_window_close'}
