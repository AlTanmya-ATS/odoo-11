# -*- coding: utf-8 -*-

import calendar
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from odoo.tools import float_compare, float_is_zero

class Asset(models.Model):
    _name = 'asset_management.asset'
    name = fields.Char(string="Asset Number", index=True,readonly=True)
    description = fields.Text("Description")
    #units = fields.Integer("Units")
    ownership_type = fields.Selection(selection=[('owned', 'Owned')
        , ('leased', 'Leased')])
    is_new = fields.Selection(selection=[('new', 'New')
        , ('used', 'Used')])
    is_in_physical_inventory = fields.Boolean()
    in_use_flag = fields.Boolean(required=True)
    parent_asset = fields.Many2one('asset_management.asset', on_delete='cascade')
    item_id = fields.Many2one('product.product', on_delete='set_null')
    category_id = fields.Many2one('asset_management.category', required=True)
    book_assets_id = fields.One2many(comodel_name="asset_management.book_assets", inverse_name="asset_id", string="Book")
    depreciation_line_ids = fields.One2many(comodel_name="asset_management.depreciation", inverse_name="asset_id", string="depreciation")
    asset_serial_number = fields.Char(string ='Serial Number' )
    asset_tag_number = fields.Many2many('asset_management.tag')
    percentage = fields.Integer(compute = '_modify_percentage')
    assignment_id = fields.One2many('asset_management.assignment',inverse_name='asset_id')
    _sql_constraints=[
        ('asset_serial_number','UNIQUE(asset_serial_number)','Serial Number already exists!')
    ]
    
    asset_with_category=fields.Boolean(related='category_id.asset_with_category')
    # sum_result=fields.Integer()
    state = fields.Selection([('draft', 'Draft'), ('open', 'Running'), ('close', 'Close')], 'Status', required=True,
                             copy=False, default='draft',
                             help="When an asset is created, the status is 'Draft'.\n"
                                  "If the asset is confirmed, the status goes in 'Running' and the depreciation lines can be posted in the accounting.\n"
                                  "You can manually close an asset when the depreciation is over. If the last line of depreciation is posted, the asset automatically goes in that status.")

    @api.model
    def create(self, values):
        values['name'] = self.env['ir.sequence'].next_by_code('asset_management.asset.Asset')
    #     record=super(Asset, self).create(values)
    #     self.env['asset_management.transaction'].create({
    #          'asset_id': record.id,
    #          'trx_type': 'addition',
    #          'trx_date': datetime.today(),
    #          })
        return super(Asset, self).create(values)

    @api.multi
    def write(self, values):
        old_value=self.category_id
        super(Asset, self).write(values)
        if 'category_id' in values:
            if self.category_id != old_value:
                for record in self:
                    self.env['asset_management.transaction'].create({
                         'asset_id': record.id,
                         'trx_type': 're_class',
                         'trx_date': datetime.today(),
                         'category_id':self.category_id.id,
                         })
                return record

    # @api.onchange('assignment_id')
    # def _onchange_assignment_id(self):
    #     for p in self.assignment_id:
    #         self.percentage +=p.percentage #self.assignment_id.percentage

    @api.depends('assignment_id')
    def _modify_percentage(self):
        for record in self:
            for assignment in record.assignment_id:
                record.percentage+=assignment.percentage

    @api.onchange('category_id')
    def onchange_category_id(self):
        if self.category_id:
                self.asset_with_category = True

    @api.constrains('assignment_id')
    def _checkpercentage(self):
        for record in self:
            if record.percentage not in (0,100):
                raise ValidationError("Assignment does not add up to 100")
    # @api.onchange('assignment_id')
    # def onchange_assignment_id(self):
    #     sum_res=0
    #     for x in self.assignment_id:
    #         sum_res+=x.percentage
    #     self.sum_result=float_compare(100.00,pre
    #                                       sum_res, precision_digits=2)

    # @api.constrains('sum_result')
    # def _check_sum(self):
    #     if len(self.assignment_id)> 0:
    #         if self.sum_result != 0 :
    #             raise ValidationError("Assignment percentage != %100 asset can not be save")

    # @api.onchange('category_id')
    # def  _onchange_category_id(self):
    #     old_value=self._origin.category_id
    #     if self.category_id:
    #          record_exist = self.env['asset_management.transaction'].search([('asset_id','=',self._context.get('id'))],limit=1)
    #          if record_exist:
    #             if self.category_id != old_value:
    #                  self.env['asset_management.transaction'].create({
    #                         'asset_id':self.id,
    #                         'trx_type': 're_class',
    #                         'trx_date': datetime.today(),
    #                       #'category_id' :self.category_id
    #                 })
    #          else:
    #             self.env['asset_management.transaction'].create({
    #                 'asset_id':self.id,
    #                 'trx_type': 'addition',
    #                 'trx_date': datetime.today(),
    #               #  'category_id':self._context.get('category_id')
    #             })


class Category(models.Model):
    _name = 'asset_management.category'
    name = fields.Char(string='Category Name',index=True)
    description = fields.Text()
    ownership_type = fields.Selection(selection=[('owned', 'Owned')
        , ('leased', 'Leased')])
    is_in_physical_inventory = fields.Boolean()
    category_books_id=fields.One2many('asset_management.category_books',inverse_name='category_id',on_delete='cascade')
    depreciation_method = fields.Selection([('linear','Linear'),('degressive','Degressive')],
    default='linear')
    asset_with_category=fields.Boolean()


class Book(models.Model):
    _name = 'asset_management.book'
    name = fields.Char(index=True)
    description = fields.Text()
    proceeds_of_sale_gain_account = fields.Many2one('account.account', on_delete='set_null')
    proceeds_of_sale_loss_account = fields.Many2one('account.account', on_delete='set_null')
    proceeds_of_loss_clearing_account = fields.Many2one('account.account', on_delete='set_null')
    cost_of_removal_gain_account = fields.Many2one('account.account', on_delete='set_null')
    cost_of_removal_loss_account = fields.Many2one('account.account', on_delete='set_null')
    cost_of_removal_clearing_account = fields.Many2one('account.account', on_delete='set_null')
    net_book_value_retired_gain_account = fields.Many2one('account.account', on_delete='set_null')
    net_book_value_retired_loss_account = fields.Many2one('account.account', on_delete='set_null')
    reval_reserve_retire_gain_account = fields.Many2one('account.account', on_delete='set_null')
    reval_reserve_retire_loss_account = fields.Many2one('account.account', on_delete='set_null')
    deferred_depreciation_reserve_account = fields.Many2one('account.account', on_delete='set_null')
    depreciation_adjustment_account = fields.Many2one('account.account', on_delete='set_null')
    book_with_cate = fields.Boolean()

    # @api.model
    # def create(self, values):
    #     values['name']=self.env['ir.sequence'].next_by_code('asset_management.book.Book')
    #     return super(Book, self).create(values)



class Book_Assets (models.Model):
    _name='asset_management.book_assets'
    name=fields.Char( string="Book Asset Number",index=True)
    book_id = fields.Many2one('asset_management.book',on_delete= 'cascade')
    asset_id = fields.Many2one('asset_management.asset',on_delete = 'cascade')
    depreciation_line_ids=fields.One2many('asset_management.depreciation',inverse_name='book_assets_id')
    current_cost = fields.Float(string = "Current Cost",
                                 compute='_amount_residual')
    salvage_value = fields.Float()
    method = fields.Selection(
        [('linear','Linear'),
         ('degressive','Degressive')
         ],
        default='linear'
    )
    life_months = fields.Integer()
    end_date=fields.Date()
    original_cost = fields.Float()
    salvage_value_type = fields.Selection(
        [('first','First Type')]
    )
    date_in_service = fields.Date(string = 'Date In Service')
    prorate_date= fields.Date(string = 'Prorate Date')
    prorate_convenction = fields.Selection(
        [('first','First Convention')]
    )
    depreciated_flag = fields.Boolean(string='Depreciated',default =True)
    method_progress_factor = fields.Float(string='Degressive Factor',default=0.3)




    @api.model
    def create(self, values):
        values['name'] = self.env['ir.sequence'].next_by_code('asset_management.book_assets.Book_Assets')
        record = super(Book_Assets, self).create(values)
        self.env['asset_management.transaction'].create({
                 'asset_id': record.asset_id.id,
                 'book_id':record.book_id.id,
                 'category_id': self.asset_id.category_id.id,
                 'trx_type': 'addition',
                 'trx_date': datetime.today(),
                 })
        return record


    @api.onchange('original_cost')
    def _onchange_original_cost(self):
        if self.original_cost:
            self.env['asset_management.transaction'].create({
                'asset_id': self.asset_id.id,
                'book_id': self.book_id.id,
                'category_id':self.asset_id.category_id.id,
                'trx_type': 'cost_adjustment',
                'trx_date': datetime.today(),
            })


    def _compute_board_undone_dotation_nb(self, depreciation_date, total_days):

        end_date = datetime.strptime(self.end_date,DF).date()
        undone_dotation_number = 0
        while depreciation_date <= end_date:
            depreciation_date = date(depreciation_date.year, depreciation_date.month,
                                     depreciation_date.day) + relativedelta(months=+self.life_months)
            undone_dotation_number += 1
        # if self.prorata:
        #     undone_dotation_number += 1
        return undone_dotation_number


    def _compute_board_amount(self, sequence, residual_amount, amount_to_depr, undone_dotation_number,
                              posted_depreciation_line_ids):
        amount = 0
        if sequence == undone_dotation_number:
            amount = residual_amount
        else:
             if self.method == 'linear':
                amount = amount_to_depr / (undone_dotation_number - len(posted_depreciation_line_ids))
                # if self.prorata:
                #     amount = amount_to_depr / self.method_number
                #     if sequence == 1:
                #         if self.method_period % 12 != 0:
                #             date = datetime.strptime(self.date, '%Y-%m-%d')
                #             month_days = calendar.monthrange(date.year, date.month)[1]
                #             days = month_days - date.day + 1
                #             amount = (amount_to_depr / self.method_number) / month_days * days
                #         else:
                #             days = (self.company_id.compute_fiscalyear_dates(depreciation_date)[
                #                         'date_to'] - depreciation_date).days + 1
                #             amount = (amount_to_depr / self.method_number) / total_days * days
             elif self.method == 'degressive':
                amount = residual_amount * self.method_progress_factor
                # if self.prorata:
                #     if sequence == 1:
                #         if self.method_period % 12 != 0:
                #             date = datetime.strptime(self.date, '%Y-%m-%d')
                #             month_days = calendar.monthrange(date.year, date.month)[1]
                #             days = month_days - date.day + 1
                #             amount = (residual_amount * self.method_progress_factor) / month_days * days
                #         else:
                #             days = (self.company_id.compute_fiscalyear_dates(depreciation_date)[
                #                         'date_to'] - depreciation_date).days + 1
                #             amount = (residual_amount * self.method_progress_factor) / total_days * days
        return amount


    @api.one
    @api.depends('original_cost', 'salvage_value', 'depreciation_line_ids.move_check', 'depreciation_line_ids.amount')
    def _amount_residual(self):
        total_amount = 0.0
        for line in self.depreciation_line_ids:
            if line.move_check:
                total_amount += line.amount
        self.current_cost = self.original_cost - total_amount - self.salvage_value




    @api.multi
    def compute_depreciation_board(self):
        self.ensure_one()

        posted_depreciation_line_ids = self.depreciation_line_ids.filtered(lambda x: x.move_check).sorted(key=lambda l: l.depreciation_date)
        unposted_depreciation_line_ids = self.depreciation_line_ids.filtered(lambda x: not x.move_check)

        # Remove old unposted depreciation lines. We cannot use unlink() with One2many field
        commands = [(2, line_id.id, False) for line_id in unposted_depreciation_line_ids]

        if self.current_cost != 0.0:
            amount_to_depr = residual_amount = self.current_cost
            # if self.prorata:
            #     # if we already have some previous validated entries, starting date is last entry + method perio
            #     if posted_depreciation_line_ids and posted_depreciation_line_ids[-1].depreciation_date:
            #         last_depreciation_date = datetime.strptime(posted_depreciation_line_ids[-1].depreciation_date, DF).date()
            #         depreciation_date = last_depreciation_date + relativedelta(months=+self.method_period)
            #     else:
            #         depreciation_date = datetime.strptime(self._get_last_depreciation_date()[self.id], DF).date()
            # else:
            # depreciation_date = 1st of January of purchase year if annual valuation, 1st of
            # purchase month in other cases
            if self.life_months >= 12:
                asset_date = datetime.strptime(self.date_in_service[:4] + '-01-01', DF).date()
            else:
                asset_date = datetime.strptime(self.date_in_service[:7] + '-01', DF).date()
            # if we already have some previous validated entries, starting date isn't 1st January but last entry + method period
            if posted_depreciation_line_ids and posted_depreciation_line_ids[-1].depreciation_date:
                last_depreciation_date = datetime.strptime(posted_depreciation_line_ids[-1].depreciation_date, DF).date()
                depreciation_date = last_depreciation_date + relativedelta(months=+self.life_months)
            else:
                depreciation_date = asset_date

            day = depreciation_date.day
            month = depreciation_date.month
            year = depreciation_date.year
            total_days = (year % 4) and 365 or 366

            undone_dotation_number = self._compute_board_undone_dotation_nb(depreciation_date, total_days)
            for x in range(len(posted_depreciation_line_ids), undone_dotation_number):
                sequence = x + 1
                amount = self._compute_board_amount(sequence, residual_amount, amount_to_depr, undone_dotation_number, posted_depreciation_line_ids)
                current_currency = self.env['res.company'].search([('id', '=', 1)])[0].currency_id
                amount = current_currency.round(amount)
                if float_is_zero(amount, precision_rounding=current_currency.rounding):
                    continue
                residual_amount -= amount
                vals = {
                    'amount': amount,
                    'asset_id': self.asset_id.id,
                    'book_id':self.book_id.id,
                    'sequence': sequence,
                    'name': (self.name or '') + '/' + str(sequence),
                    'remaining_value': residual_amount,
                    'depreciated_value': self.original_cost - (self.salvage_value + residual_amount),
                    'depreciation_date': depreciation_date.strftime(DF),
                }
                commands.append((0, False, vals))
                # Considering Depr. Period as months
                depreciation_date = date(year, month, day) + relativedelta(months=+self.life_months)
                day = depreciation_date.day
                month = depreciation_date.month
                year = depreciation_date.year

        self.write({'depreciation_line_ids': commands})

        return True



    @api.multi
    def _compute_entries(self, date, group_entries=False):
        depreciation_ids = self.env['account.asset.depreciation.line'].search([
            ('asset_id', 'in', self.ids), ('depreciation_date', '<=', date),
            ('move_check', '=', False)])
        if group_entries:
            return depreciation_ids.create_grouped_move()
        return depreciation_ids.create_move()

    @api.multi
    def create_grouped_move(self, post_move=True):
        created_moves = self.env['account.move']
        current_currency = self.env['res.company'].search([('id','=',1)])[0].currency_id
        jounal_id=self.env['account.journal'].search([('id','=',3)])[0].id
        for line in self:
            category_id = line.asset_id.category_id
            depreciation_date = self.env.context.get(
                'depreciation_date') or line.depreciation_date or fields.Date.context_today(self)
            asset_cost_account = line.env['assset_management.category_books'].search( [('book_id', '=', book_id), ('category_id', '=', category_id)])[0].asset_cost_account
            depreciation_expense_account=line.env['assset_management.category_books'].search([('book_id','=',book_id),('category_id','=',category_id)])[0].depreciation_expense_account
            partner_id=line.env['asset_management.source_line'].search([('asset_id','=',asset_id)])[0].invoice_id.partner_id
            amount = current_currency.compute(line.amount, current_currency)
            move_line_1 = {
                'name': line.asset_id.name,
                'account_id':asset_cost_account.id,
                'debit': 0.0 ,
                'credit': amount ,
                'journal_id':jounal_id,
                'analytic_account_id': False,
            }
            move_line_2 = {
                'name': line.asset_id.name,
                'account_id':depreciation_expense_account.id,
                'credit': 0.0 ,
                'debit': amount ,
                'journal_id': jounal_id,
                'analytic_account_id':  False,
            }
            move_vals = {
                'ref':line.asset_id.name,
                'date': depreciation_date or False,
                'journal_id': jounal_id,
                'line_ids': [(0, 0, move_line_1), (0, 0, move_line_2)],
            }
            move = self.env['account.move'].create(move_vals)
            line.write({'move_id': move.id, 'move_check': True})
            created_moves |= move

            if post_move and created_moves:
                created_moves.filtered(
                    lambda m: any(m.asset_depreciation_ids.mapped('asset_id.category_id.open_asset'))).post()
            return [x.id for x in created_moves]


class Assignment(models.Model):
    _name = 'asset_management.assignment'
    name = fields.Char(string="Assignment",readonly='True',index=True)
    book_assets_id = fields.Many2one('asset_management.book_assets',on_delete = 'cascade')
    book_id = fields.Many2one("asset_management.book", string="Book",on_delete = 'cascade' )
    asset_id = fields.Many2one("asset_management.asset", string="Asset", on_delete='cascade')
    expence_Acc_ID = fields.Many2one('account.account', on_delete='set_null')
    responsible_id = fields.Many2one('hr.employee', on_delete='set_null')
    location_id = fields.Many2one('asset_management.location')
    is_not_used = fields.Boolean( defult = False )
    end_use_date = fields.Date()
    transfer_date = fields.Date()
    comments = fields.Text()
    percentage=fields.Integer(default = 100)
    # units = fields.Integer()
    # units_to_assign= fields.Integer(string = "Units to Assign ,compute = '_get_units_to_assign')
    # @api.depends('responsible_id')
    # def _get_default_location(self):
    #    for record in self:
    #        record.location_id=record.responsible_id.work_location
    # @api.depends('units')
    # def _get_units_to_assign(self):
    #     for record in self:
    #       record.units_to_assign= record.book_assets_id.asset_id.units-record.units

    @api.constrains('percentage')
    def _check_valid_percentage(self):
        for record in self:
            if not record.percentage in range(0,101):
                raise ValidationError("Invalid value")


    @api.model
    def create(self, values):
        values['name']=self.env['ir.sequence'].next_by_code('asset_management.assignment.Assignment')
        return super(Assignment, self).create(values)

    @api.onchange('responsible_id','location_id')
    def _onchange_assignment(self):
        if self.responsible_id or self.location_id:
            self.env['asset_management.transaction'].create({
                'asset_id':self.asset_id.id,
                'category_id':self.asset_id.category_id.id,
                'trx_type': 'transfer',
                'trx_date': datetime.today()
                    })

    @api.onchange('end_use_date')
    def onchange_method(self):
       if self.end_use_date :
           self.is_not_used = True

    # @api.onchange('book_id')
    # def onchange_method(self):
    #     if self.book_id :
    #         x=[]
    #         result = self.env['asset_management.book_assets'].search([('book_id', '=', self.book_id.id)])
    #         for r in result:
    #             x+=[r.asset_id.id]
    #
    #         # result1=self.env['asset_management.asset'].search([('id','=',result.asset_id.id)])
    #         # res=result1.mapped('id')
    #         return {'domain':{'asset_id':[('id', 'in',x)]
    #                           }}


class Source_Line(models.Model):
    _name = 'asset_management.source_line'
    name = fields.Char(string="Source Line Number",readonly=True,index=True)
    asset_id = fields.Many2one('asset_management.asset',on_delete = 'cascade')
    source_type = fields.Selection(
        [
            ('invoice','Invoice'),
            ('po','Purchase Order')
        ]
    )
    #source_id = fields.Char(sting='Source')
    invoice_id = fields.Many2one(comodel_name="account.invoice", string="invoice")
    po_id = fields.Many2one(comodel_name="purchase.order", string="purchase order")
    #po_line_id=fields.Many2one(comodel_name="purchase.order.line", string="purchase order",compute="_get_po_line")
    amount = fields.Float('Amount')
    description = fields.Text()

    @api.model
    def create(self, values):
        values['name']=self.env['ir.sequence'].next_by_code('asset_management.source_line.Source_Line')
        return super(Source_Line, self).create(values)


class Depreciation(models.Model):
    _name = 'asset_management.depreciation'
    name = fields.Char(string="Depreciation Number",readonly=True,index=True)
    book_assets_id = fields.Many2one('asset_management.book_assets', on_delte='cascade')
    asset_id = fields.Many2one('asset_management.asset', on_delte='cascade')
    book_id = fields.Many2one('asset_management.book', on_delte='cascade')
    sequence = fields.Integer(required=True)
    amount = fields.Float(string='Current Depreciation', digits=0, )
    remaining_value = fields.Float(string='Next Period Depreciation', digits=0, required=True)
    depreciated_value = fields.Float(string='Cumulative Depreciation', required=True)
    depreciation_date = fields.Date('Depreciation Date', index=True)
    move_id = fields.Many2one('account.move', string='Depreciation Entry')
    move_check = fields.Boolean(compute='_get_move_check', string='Linked', track_visibility='always', store=True)
    move_posted_check = fields.Boolean(compute='_get_move_posted_check', string='Posted', track_visibility='always',
                                       store=True)

    @api.multi
    @api.depends('move_id')
    def _get_move_check(self):
        for line in self:
            line.move_check = bool(line.move_id)

    @api.multi
    @api.depends('move_id.state')
    def _get_move_posted_check(self):
        for line in self:
            line.move_posted_check = True if line.move_id and line.move_id.state == 'posted' else False

    @api.multi
    def create_move(self, post_move=True):
        created_moves = self.env['account.move']
        prec = self.env['decimal.precision'].precision_get('Account')
        current_currency = self.env['res.company'].search([('id','=',1)])[0].currency_id
        jounal_id=self.env['account.journal'].search([('id','=',3)])[0].id
        for line in self:
            if line.move_id:
                raise UserError(
                    _('This depreciation is already linked to a journal entry! Please post or delete it.'))
            category_id = line.asset_id.category_id
            depreciation_date = self.env.context.get(
                'depreciation_date') or line.depreciation_date or fields.Date.context_today(self)
            asset_cost_account = line.env['assset_management.category_books'].search( [('book_id', '=', book_id), ('category_id', '=', category_id)])[0].asset_cost_account
            depreciation_expense_account=line.env['assset_management.category_books'].search([('book_id','=',book_id),('category_id','=',category_id)])[0].depreciation_expense_account
            partner_id=line.env['asset_management.source_line'].search([('asset_id','=',asset_id)])[0].invoice_id.partner_id
            amount = current_currency.with_context(date=depreciation_date).compute(line.amount, current_currency)
            asset_name = line.asset_id.name + ' (%s/%s)' % (line.sequence, len(line.asset_id.depreciation_line_ids))
            move_line_1 = {
                'name': asset_name,
                'account_id':asset_cost_account.id,
                'debit': 0.0 if float_compare(amount, 0.0, precision_digits=prec) > 0 else -amount,
                'credit': amount if float_compare(amount, 0.0, precision_digits=prec) > 0 else 0.0,
                'journal_id':jounal_id,
                'partner_id': partner_id.id,
                'analytic_account_id': False,
                'currency_id':  current_currency.id or False,
                'amount_currency':   - 1.0 * line.amount or 0.0,
            }
            move_line_2 = {
                'name': asset_name,
                'account_id':depreciation_expense_account.id,
                'credit': 0.0 if float_compare(amount, 0.0, precision_digits=prec) > 0 else -amount,
                'debit': amount if float_compare(amount, 0.0, precision_digits=prec) > 0 else 0.0,
                'journal_id': jounal_id,
                'partner_id': partner_id.id,
                'analytic_account_id':  False,
                'currency_id': current_currency.id or False,
                'amount_currency':  line.amount or 0.0,
            }
            move_vals = {
                'ref': line.asset_id.name,
                'date': depreciation_date or False,
                'journal_id': jounal_id,
                'line_ids': [(0, 0, move_line_1), (0, 0, move_line_2)],
            }
            move = self.env['account.move'].create(move_vals)
            line.write({'move_id': move.id, 'move_check': True})
            created_moves |= move

            if post_move and created_moves:
                created_moves.filtered(
                    lambda m: any(m.asset_depreciation_ids.mapped('asset_id.category_id.open_asset'))).post()
            return [x.id for x in created_moves]

    @api.multi
    def create_grouped_move(self, post_move=True):
        if not self.exists():
            return []


        created_moves = self.env['account.move']
        category_id = self[0].asset_id.category_id  # we can suppose that all lines have the same category
        depreciation_date = self.env.context.get('depreciation_date') or fields.Date.context_today(self)
        jounal_id = self.env['account.journal'].search([('id', '=', 3)])[0].id
        amount = 0.0
        for line in self:
            asset_cost_account = line.env['assset_management.category_books'].search(
            [('book_id', '=', book_id), ('category_id', '=', category_id)])[0].asset_cost_account
            depreciation_expense_account = line.env['assset_management.category_books'].search(
                [('book_id', '=', book_id), ('category_id', '=', category_id)])[0].depreciation_expense_account
            # Sum amount of all depreciation lines
            # company_currency = line.asset_id.company_id.currency_id
            current_currency = self.env['res.company'].search([('id', '=', 1)])[0].currency_id
            amount += current_currency.compute(line.amount, current_currency)

        name = category_id.name + _(' (grouped)')
        move_line_1 = {
            'name': name,
            'account_id': asset_cost_account.id,
            'debit': 0.0,
            'credit': amount,
            'journal_id':jounal_id.id,
            'analytic_account_id':  False,
        }
        move_line_2 = {
            'name': name,
            'account_id': depreciation_expense_account.id,
            'credit': 0.0,
            'debit': amount,
            'journal_id': jounal_id.id,
            'analytic_account_id':  False,
        }
        move_vals = {
            'ref': category_id.name,
            'date': depreciation_date or False,
            'journal_id': journal_id.id,
            'line_ids': [(0, 0, move_line_1), (0, 0, move_line_2)],
        }
        move = self.env['account.move'].create(move_vals)
        self.write({'move_id': move.id, 'move_check': True})
        created_moves |= move

        if post_move and created_moves:
            self.post_lines_and_close_asset()
            created_moves.post()
        return [x.id for x in created_moves]

    # @api.multi
    # def post_lines_and_close_asset(self):
    #     # we re-evaluate the assets to determine whether we can close them
    #     for line in self:
    #         line.log_message_when_posted()
    #         asset = line.asset_id
    #         current_cost=line.env['asset_management.book_asset'].search([('asset_id','=',asset_id),('book_id','=',book_id)])[0].current_cost
    #         current_currency = self.env['res.company'].search([('id', '=', 1)])[0].currency_id
    #         if current_currency.is_zero(current_cost):
    #             asset.message_post(body=_("Document closed."))
    #             asset.write({'state': 'close'})
    #
    # @api.multi
    # def log_message_when_posted(self):
    #     def _format_message(message_description, tracked_values):
    #         message = ''
    #         if message_description:
    #             message = '<span>%s</span>' % message_description
    #         for name, values in tracked_values.items():
    #             message += '<div> &nbsp; &nbsp; &bull; <b>%s</b>: ' % name
    #             message += '%s</div>' % values
    #         return message
    #
    #     for line in self:
    #         if line.move_id and line.move_id.state == 'draft':
    #             partner_name = line.asset_id.partner_id.name
    #             currency_name = line.asset_id.currency_id.name
    #             msg_values = {_('Currency'): currency_name, _('Amount'): line.amount}
    #             if partner_name:
    #                 msg_values[_('Partner')] = partner_name
    #             msg = _format_message(_('Depreciation line posted.'), msg_values)
    #             line.asset_id.message_post(body=msg)
    #
    # @api.multi
    # def unlink(self):
    #     for record in self:
    #         if record.move_check:
    #             if record.asset_id.category_id.type == 'purchase':
    #                 msg = _("You cannot delete posted depreciation lines.")
    #             else:
    #                 msg = _("You cannot delete posted installment lines.")
    #             raise UserError(msg)
    #     return super(AccountAssetDepreciationLine, self).unlink()

    @api.model
    def create(self, values):
        values['name'] = self.env['ir.sequence'].next_by_code('asset_management.depreciation.Depreciation')
        return super(Depreciation,self).create(values)


class Retirement (models.Model):
    _name = 'asset_management.retirement'
    name=fields.Char(string="Retirement Number",readonly=True,index=True)
    book_assets_id = fields.Many2one('asset_management.book_assets',on_delete = 'cascade')
    book_id=fields.Many2one('asset_management.book',on_delete = 'cascade')
    asset_id = fields.Many2one('asset_management.asset', required=True, on_delete='cascade')
    retire_date = fields.Date(string = 'Retire Date')
    comments = fields.Text(string = "Comments")
    current_cost = fields.Float(string= "Current Cost")
    units_retired = fields.Integer(string ='Units Retired')
    current_units = fields.Integer(string="Units to Assign"
                                      , compute='_get_current_units')
    gain_loss_amount=fields.Float()
    proceeds_of_sale = fields.Float()
    cost_of_removal= fields.Float()
   # sold_to=fields.Char()
    partner_id = fields.Many2one(comodel_name="res.partner", string="Sold To")
    check_invoice= fields.Char()

    @api.model
    def _get_current_units(self):
        return self.book_assets_id.asset_id.units - self.units_retired

    @api.model
    def create(self, values):
        values['name'] = self.env['ir.sequence'].next_by_code('asset_management.retirement.Retirement')
        return super(Retirement,self).create(values)


class Category_Books(models.Model):
    _name= 'asset_management.category_books'
    name = fields.Char(string="Category Books Num",index=True)
    category_id = fields.Many2one('asset_management.category',required=True
                                        ,on_delete='cascade',string='Category')
    book_id = fields.Many2one('asset_management.book',on_delete='cascade',string='Book Num')
    asset_cost_account = fields.Many2one('account.account',on_delete='set_null')
    asset_clearing_account = fields.Many2one('account.account', on_delete='set_null')
    depreciation_expense_account = fields.Many2one('account.account', on_delete='set_null')
    accumulated_expense_account = fields.Many2one('account.account', on_delete='set_null')
    bonus_expense_account = fields.Many2one('account.account', on_delete='set_null')
    bonus_reserve_account = fields.Many2one('account.account', on_delete='set_null')
    cip_cost_account =fields.Many2one('account.account', on_delete='set_null')
    cip_clearing_account = fields.Many2one('account.account', on_delete='set_null')
    book_with_cate=fields.Boolean(related='book_id.book_with_cate')
    test_field=fields.Boolean()
    @api.model
    def create(self, values):
        values['name'] = self.env['ir.sequence'].next_by_code('asset_management.category_books.Category_Books')
        return super(Category_Books, self).create(values)

    @api.onchange('book_id')
    def onchange_method(self):
        if self.book_id:
            # book_search=self.env['asset_management.book'].search([('id','=',self.book_id.id)])[0]
            # if book_search:
                self.book_with_cate = True


class Transaction (models.Model):
    _name = 'asset_management.transaction'
    name =fields.Char(string="Transaction Number",readonly=True,index=True)
   # book_assets_id= fields.Many2one('asset_management.book_assets',required =True,on_delte = 'cascade')
    asset_id=fields.Many2one('asset_management.asset',on_delete='cascade',string="Asset")
    book_id=fields.Many2one('asset_management.book',on_delete='cascade',string="Book")
    category_id = fields.Many2one("asset_management.category", string="Category",on_delete='cascade')
    trx_type = fields.Selection(
        [
		     ('addition','Addition'),
			('re_class','Re_Class'),
            ('transfer','Transfer'),
            ('cost_adjustment','Cost Adjustment')
        ]
    )
    trx_date = fields.Date('Transaction Date')
    cost = fields.Float('Cost')
    trx_details = fields.Text('Trx Details')
    period = fields.Selection(
        [('1','JAN'),
         ('2','FEB'),
         ('3','MAR')]
    )

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('asset_management.transaction.Transaction')
        return super(Transaction, self).create(vals)

    # @api.depends('asset_id')
    # def _get_category_id(self):
    #     for record in self:
    #         record.category_id = record.asset_id.category_id.id
    #         return record.category_id


    # @api.depends('asset_id')
    # def _get_book_id(self):
    #         asset_in_book= self.env['asset_management.book_assets'].search([('asset_id','=',self.asset_id.id)])
    #         self.book_id=asset_in_book.book_id






class AssetTag(models.Model):
    _name = 'asset_management.tag'
    name = fields.Char()


class AssetLocation(models.Model):
    _name = 'asset_management.location'
    name = fields.Char()
    latitude = fields.Char(default="33.512888")
    longitude = fields.Char(defualt="36.298101")


