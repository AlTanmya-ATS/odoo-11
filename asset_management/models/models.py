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
    description = fields.Text("Description" ,required=True)
    ownership_type = fields.Selection(selection=[('owned', 'Owned')], default='owned')
    is_new = fields.Selection(selection=[('new', 'New')
        , ('used', 'Used')],default='new')
    is_in_physical_inventory = fields.Boolean(default=True)
    in_use_flag = fields.Boolean(default=True)
    parent_asset = fields.Many2one('asset_management.asset', on_delete='cascade')
    item_id = fields.Many2one('product.product', on_delete='set_null')
    category_id = fields.Many2one('asset_management.category', required=True,domain=[('active','=',True)])
    book_assets_id = fields.One2many(comodel_name="asset_management.book_assets", inverse_name="asset_id", string="Book",on_delete='cascade')
    depreciation_line_ids = fields.One2many(comodel_name="asset_management.depreciation", inverse_name="asset_id", string="depreciation",on_delete='cascade')
    asset_serial_number = fields.Char(string ='Serial Number' )
    asset_tag_number = fields.Many2many('asset_management.tag')
    _sql_constraints=[
        ('asset_serial_number','UNIQUE(asset_serial_number)','Serial Number already exists!')
    ]
    asset_with_category=fields.Boolean(related='category_id.asset_with_category')
    #source_line_id=fields.One2many('asset_management.source_line',string='Source Line',inverse_name='asset_id',on_delete='cascade')
    # default_book=fields.Many2one('asset_management.book',required=True)
    # state=fields.Selection([('draft','Draft'),('capitalize','Capitalize'),('retired','Retired')] ,default="draft",string='Status',required=True,copy=False,
    #                        help="When an asset is created the status is Draft\n"
    #                             "If a Book , an Assignment and a Source Line are added the statues goes in 'Capitalized' and the depreciation can be computed\n"
    #                             "You can manually close an asset by pressing 'Set To Retire' button ")

    currency_id = fields.Many2one('res.currency', string='Currency', required=True, readonly=True,default=lambda self: self.env.user.company_id.currency_id.id)
    entry_asset_count = fields.Integer(compute='_entry_asset_count', string='# Asset Entries')
    transaction_id=fields.One2many('asset_management.transaction',inverse_name="asset_id",on_delete="cascade")
    category_invisible=fields.Boolean()

    # @api.multi
    # def validation(self):
    #     if not self.book_assets_id :
    #         raise ValidationError("The fallowing fields should be entered in order to move to 'capitalize' state "
    #                               "and be able to compute deprecation:"
    #                               "\n-Book"
    #                             )
    #     else:
    #         for assetstate in self.book_assets_id:
    #             if assetstate.state != 'open':
    #                 raise ValidationError ('books should be in running state..!')
    #             else:
    #                 self.state='capitalize'
    #                 for record in self.book_assets_id:
    #                     if not self.env['asset_management.transaction'].search([('asset_id','=', record.asset_id.id),('book_id','=', record.book_id.id),('trx_type','=','addition')]):
    #                         self.env['asset_management.transaction'].create({
    #                             'asset_id': record.asset_id.id,
    #                             'book_id': record.book_id.id,
    #                             'category_id': record.asset_id.category_id.id,
    #                             'trx_type': 'addition',
    #                             'trx_date': datetime.today(),
    #                             'trx_details': 'New Asset ' + record.asset_id.name + ' Is Added to the Book: ' + record.book_id.name
    #                         })

    # @api.multi
    # def set_to_draft(self):
    #     self.state='draft'

    @api.multi
    def open_asset_entries(self):
        move_ids = []
        for asset in self:
            for depreciation_line in asset.depreciation_line_ids:
                if depreciation_line.move_id:
                    move_ids.append(depreciation_line.move_id.id)
        return {
            'name': _('Journal Entries'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', move_ids)],
        }

    @api.multi
    @api.depends('depreciation_line_ids.move_id')
    def _entry_asset_count(self):
        for asset in self:
            res = asset.env['asset_management.depreciation'].search_count(
                [('asset_id', '=',asset.id),('move_id','!=',False)])
            asset.entry_asset_count = res or 0

    @api.model
    def create(self, values):
        values['name'] = self.env['ir.sequence'].next_by_code('asset_management.asset.Asset')
        if 'book_assets_id' not in values:
            raise ValidationError('Asset must be added to a book')
        return super(Asset , self).create(values)


    @api.multi
    def generate_mas_entries(self,date_from,date_to,post_entries,book_id):
        new_moved_lines=[]
        old_moved_lines=[]
        capitalized_asset=self.env['asset_management.book_assets'].search([('state','=','open'),('book_id','=',book_id)])
        if date_from < capitalized_asset[0].book_id.start_date or date_to > capitalized_asset[0].book_id.end_date:
            raise ValidationError("Period of generate entries is not in current fiscal period ")
        for entries in capitalized_asset:
            dep_line = self.env['asset_management.depreciation'].search([('asset_id', '=', entries.asset_id.id)
                              ,('depreciation_date', '<=', date_to),('depreciation_date','>=',date_from),('move_posted_check','=',False)])
            trx_lines=self.env['asset_management.transaction'].search([('asset_id', '=', entries.asset_id.id),
                                      ('trx_date', '<=', date_to),('trx_date','>=',date_from),('move_posted_check','=',False)])
            for deprecation in dep_line:
                if not deprecation.move_check:
                    deprecation.create_move()
                    new_moved_lines +=deprecation
                else:
                    old_moved_lines +=deprecation

            for trx in trx_lines:
                if not trx.move_check :
                    if trx.trx_type == 'full_retirement' or trx.trx_type == 'partial_retirement':
                        trx.generate_retirement_journal()
                        new_moved_lines += trx
                    else:
                        trx.create_trx_move()
                        new_moved_lines+=trx
                else:
                    old_moved_lines+=trx
        if not post_entries:
          return new_moved_lines
        else:
            new_moved_lines+=old_moved_lines
            return new_moved_lines


class Category(models.Model):
    _name = 'asset_management.category'
    name = fields.Char(string='Category Name',index=True,required=True)
    description = fields.Text(required=True)
    ownership_type = fields.Selection(selection=[('owned', 'Owned')],default='owned')
    is_in_physical_inventory = fields.Boolean(default=True)
    category_books_id=fields.One2many('asset_management.category_books',inverse_name='category_id',on_delete='cascade',)
    depreciation_method = fields.Selection([('linear','Linear'),('degressive','Degressive')],
    default='linear')
    asset_with_category=fields.Boolean()
    active = fields.Boolean(default=True)
    _sql_constraints=[
        ('category_name','UNIQUE(name)','Category name already exist..!')
    ]

    @api.model
    def create(self, values):
       if 'category_books_id' not in values:
           raise ValidationError('Category must be added to a book')
       return super(Category, self).create(values)



class Book(models.Model):
    _name = 'asset_management.book'
    name = fields.Char(index=True,required=True)
    description = fields.Text(required=True)
    company_id=fields.Many2one('res.company', string='Company',required=True,default=lambda self: self.env['res.company']._company_default_get('asset_management.book'))
    # proceeds_of_sale_gain_account = fields.Many2one('account.account', on_delete='set_null')
    # proceeds_of_sale_loss_account = fields.Many2one('account.account', on_delete='set_null')
    # proceeds_of_loss_clearing_account = fields.Many2one('account.account', on_delete='set_null')
    cost_of_removal_gain_account = fields.Many2one('account.account', on_delete='set_null')
    cost_of_removal_loss_account = fields.Many2one('account.account', on_delete='set_null')
    # cost_of_removal_clearing_account = fields.Many2one('account.account', on_delete='set_null')
    # net_book_value_retired_gain_account = fields.Many2one('account.account', on_delete='set_null')
    # net_book_value_retired_loss_account = fields.Many2one('account.account', on_delete='set_null')
    # reval_reserve_retire_gain_account = fields.Many2one('account.account', on_delete='set_null')
    # reval_reserve_retire_loss_account = fields.Many2one('account.account', on_delete='set_null')
    # deferred_depreciation_reserve_account = fields.Many2one('account.account', on_delete='set_null')
    # depreciation_adjustment_account = fields.Many2one('account.account', on_delete='set_null')
    book_with_cate = fields.Boolean()
    active=fields.Boolean(default=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True,compute="_compute_currency")
    start_date=fields.Date(required=True)
    end_date=fields.Date(required=True)
    fiscal_year=fields.Char(compute="_compute_fiscal_year")
    _sql_constraints = [
        ('book_name', 'UNIQUE(name)', 'Book name already exist..!')
    ]

    @api.constrains('start_date','end_date')
    def _check_dates(self):
        if self.end_date <= self.start_date:
            raise ValidationError("Closing Date cannot be set before Beginning Date. ")
        if self.company_id.fiscalyear_lock_date:
            if self.company_id.fiscalyear_lock_date > self.start_date:
                raise ValidationError("Start date must be after fiscal year lock date,"
                                      "\n change the start date or the fiscal year date in accounting ")

    @api.depends('end_date','start_date')
    def _compute_fiscal_year(self):
        for record in self:
            if record.start_date:
                record.fiscal_year =str(datetime.strptime(record.start_date, DF).strftime("%Y"))
                    # datetime.strptime(record.start_date,DF).year

    @api.depends('company_id')
    def _compute_currency(self):
        for record in self:
            record.currency_id=record.company_id.currency_id.id


class BookAssets (models.Model):
    _name='asset_management.book_assets'
    name=fields.Char( string="Book Asset Number",index=True)
    book_id = fields.Many2one('asset_management.book',on_delete= 'cascade',required=True,)
    asset_id = fields.Many2one('asset_management.asset',on_delete = 'cascade',readonly=True,string='Asset')
    depreciation_line_ids=fields.One2many(comodel_name='asset_management.depreciation',inverse_name='book_assets_id',on_delete='cascade')
    depreciation_line_length=fields.Integer(compute="_depreciation_line_length")
    residual_value = fields.Float(string = "Residual Value",compute='_amount_residual',required=True)
    salvage_value = fields.Float(compute='_compute_salvage_value')
    method = fields.Selection(
        [('linear','Linear'),
         ('degressive','Degressive')
         ],required=True,string='Depreciation Method',default='linear',)
    life_months = fields.Integer(required=True,)
    end_date=fields.Date()
    original_cost = fields.Float(string='Original cost', required=True)
    current_cost=fields.Float(required=True)
    salvage_value_type = fields.Selection(
        [('amount','Amount'),('percentage','Percentage')],default='amount'
    )
    salvage_value_amount=fields.Float(string='Salvage Value Amount',)
    date_in_service = fields.Date(string = 'Date In Service',required=True,)
    prorate_date= fields.Date(string = 'Prorate Date',compute="_compute_prorate_date")
    # prorate_convenction = fields.Selection(
    #     [('first','First Convention')]
    # )
    depreciated_flag = fields.Boolean(string='Depreciated',default =True)
    method_progress_factor = fields.Float(string='Degressive Factor',default=0.3)
    method_number=fields.Integer(string='Number of Depreciation',help="The number of depreciations needed to depreciate your asset")
    # company_id = fields.Many2one('res.company', string='Company',default=lambda self: self.env['res.company']._company_default_get('asset_management.book_assets'))
    entry_count = fields.Integer(compute='_asset_entry_count', string='# Asset Entries')
    method_time = fields.Selection([('number', 'Number of Entries'), ('end', 'Ending Date')], string='Time Method',required=True,default= 'number',
                                   help="Choose the method to use to compute the dates and number of entries.\n"
                                        "  * Number of Entries: Fix the number of entries and the time between 2 depreciations.\n"
                                        "  * Ending Date: Choose the time between 2 depreciations and the date the depreciations won't go beyond.")
    state = fields.Selection([('draft', 'Draft'), ('open', 'Capitalize'), ('close', 'Close')], 'Status', required=True,
                             copy=False, default='draft',
                             help="When an asset is created, the status is 'Draft'.\n"
                                  "If the asset is confirmed, the status goes in 'Running' and the depreciation lines can be posted in the accounting.\n"
                                  "You can manually close an asset when the depreciation is over. If the last line of depreciation is posted, the asset automatically goes in that status.")
    # asset_state=fields.Selection(related='asset_id.state')
    assignment_id=fields.One2many(comodel_name='asset_management.assignment',inverse_name='book_assets_id',on_delete='cascade')
    percentage = fields.Float(compute='_modify_percentage')
    category_id = fields.Many2one('asset_management.category')
    source_line_ids=fields.One2many('asset_management.source_line','book_assets_id',on_delete='cascade')
    old_amount=fields.Float(compute="_amount_in_source_line")
    new_amount = fields.Float()
    _sql_constraints=[('unique_book_id_on_asset','UNIQUE(asset_id,book_id)','asset already added to this book')]
    accumulated_value=fields.Float(readonly=True)
    net_book_value=fields.Float(compute='_compute_net_book_value')
    current_cost_from_retir=fields.Boolean()

    @api.constrains('date_in_service')
    def _check_date_of_service(self):
        if self.date_in_service > self.book_id.end_date or self.date_in_service < self.book_id.start_date:
            raise ValidationError("Date in service must be in fiscal period from " + self.book_id.start_date+ " to " +self.book_id.end_date+
                                  "\nchange the date in service or the fiscal period")

    @api.depends('accumulated_value','current_cost')
    def _compute_net_book_value(self):
       for record in self:
           record.net_book_value = record.current_cost - record.accumulated_value

    @api.onchange('current_cost')
    def _onchange_current_cost(self):
        if self.state == 'draft':
            self.original_cost=self.current_cost

    @api.onchange('assignment_id')
    def _onchange_assignment(self):
        if self.assignment_id and not self.source_line_ids:
            warning = {
                'title': _('Warning!'),
                'message': _('Add source line to asset..!'),
            }
            return {'warning': warning}

    @api.depends('source_line_ids')
    def _amount_in_source_line(self):
        for record in self:
            for source in record.source_line_ids:
                    record.old_amount += source.amount
            # if len(record.source_line_ids) == 1:
            #     record.new_amount = record.old_amount

    @api.onchange('old_amount')
    def _onchange_amount(self):
        for record in self:
            if record.old_amount:
                record.current_cost += (record.old_amount - record.new_amount)
                record.new_amount=record.old_amount

    @api.constrains('source_line_ids')
    def _amount_constraint(self):
        for record in self:
            if record.current_cost < record.old_amount :
                raise ValidationError('amount in source lines must not be bigger than current value')

    @api.model
    def create(self, values):
        values['name'] = self.env['ir.sequence'].next_by_code('asset_management.book_assets.BookAssets')
        record = super(BookAssets, self).create(values)
        if 'assignment_id' not in values:
            raise ValidationError ('Assignment must be added in book ('+str(record.book_id.name)+')')
        if 'source_line_ids' not in values:
            raise ValidationError ('Source line must be added to book ('+str(record.book_id.name)+')')

        # self.env['asset_management.transaction'].create({
        #     'asset_id': record.asset_id.id,
        #     'book_id': record.book_id.id,
        #     'category_id': record.asset_id.category_id.id,
        #     'trx_type': 'addition',
        #     'trx_date': datetime.today(),
        #     'trx_details': 'New Asset ' +record.asset_id.name + ' Is Added to the Book: ' + record.book_id.name
        # })

        # self.env['asset_management.transaction'].create({
        #     'asset_id': record.asset_id.id,
        #     'book_id': record.book_id.id,
        #     'category_id': record.asset_id.category_id.id,
        #     'trx_type': 'cost_adjustment',
        #     'trx_date': datetime.today(),
        #     'trx_details': 'Old Gross Value  Is: '+str(0.00) + '\nNew Gross Vale Is: ' + str(record.original_cost),
        #     'cost':record.original_cost
        # })
        # return record

    @api.multi
    def write(self, values):
        old_gross_value = self.current_cost
        old_category = self.category_id
        super(BookAssets, self).write(values)
        if not self.source_line_ids:
            raise  ValidationError('Source line must be added to book')
        if self.state == 'draft':
            if 'category_id' in values:
                if self.category_id != old_category:
                    self.asset_id.category_id=self.category_id.id
                    new_depreciation_expense_account = self.env['asset_management.category_books'].search(
                        [('book_id', '=', self.book_id.id),
                         ('category_id', '=', self.category_id.id)]).depreciation_expense_account
                    for assignment in self.assignment_id:
                        assignment.depreciation_expense_account = new_depreciation_expense_account
        elif self.state == 'open':
            for record in self:
                if 'current_cost' in values:
                    if not 'current_cost_from_retir' in values :
                        self.env['asset_management.transaction'].create({
                            'asset_id': record.asset_id.id,
                            'book_id': record.book_id.id,
                            'category_id': record.category_id.id,
                            'trx_type': 'cost_adjustment',
                            'trx_date': datetime.today(),
                            'trx_details': 'Old Gross Value  Is: ' + str(old_gross_value) + '\nNew Gross Vale Is:%s ' %self.current_cost,
                            'cost':self.current_cost - old_gross_value
                        })
                        self.compute_depreciation_board()

                if 'category_id' in values:
                    if self.category_id != old_category:
                        record.env['asset_management.transaction'].create({
                            'asset_id': record.asset_id.id,
                            'book_id':record.book_id.id,
                            'trx_type': 're_class',
                            'trx_date': datetime.today(),
                            'category_id': record.category_id.id,
                            'old_category': old_category.id,
                            'trx_details': 'old category : ' + old_category.name + '\nnew category : ' + record.category_id.name
                        })
                    return record

    @api.one
    @api.depends('date_in_service')
    def _compute_prorate_date(self):
        for record in self:
            if record.date_in_service:
                asset_date = datetime.strptime(record.date_in_service[:7] + '-01', DF).date()
                record.prorate_date=asset_date

    @api.onchange('book_id')
    def domain_for_book_id(self):
        if not self.asset_id:
            return

        category = self.asset_id.category_id
        if not category:
            warning = {
                'title': _('Warning!'),
                'message': _('You must first select a category!'),
            }
            return {'warning': warning}
        else:
            if self.book_id and self.category_id:
                cat = []
                category_domain = self.env['asset_management.category_books'].search(
                    [('book_id', '=', self.book_id.id)])
                for category in category_domain:
                    if category.category_id.active:
                        cat.append(category.category_id.id)
                return {'domain': {'category_id': [('id', 'in', cat)]
                                   }}
            else:
                res=[]
                # default_book=self._context.get('default_book')
                book_domain=self.env['asset_management.category_books'].search([('category_id','=',self._context.get('category_id'))])
                for book in book_domain:
                    if book.book_id.active :
                        res.append(book.book_id.id)

                return {'domain': {'book_id': [('id', 'in', res)]
                        }}

    @api.onchange('category_id')
    def _onchange_category_id(self):
        if self.category_id:
            res = []
            book_domain = self.env['asset_management.category_books'].search(
                [('category_id', '=',self.category_id.id)])
            for book in book_domain:
                if book.book_id.active:
                    res.append(book.book_id.id)
            return {'domain': {'book_id': [('id', 'in', res)]
                               }}


    @api.constrains('original_cost')
    def _original_cost_cons(self):
        for rec in self:
            if rec.original_cost == 0:
                raise ValidationError('original cost  value must not be zero')

    @api.multi
    def validate(self):
        if not self.assignment_id and not self.source_line_ids:
            raise UserError("The fallowing fields should be entered in order to move to 'open' state "
                                  "and be able to compute deprecation:"
                                  "-\n Assignment"
                            "\n Source Line")
        elif not self.assignment_id:
            raise UserError("You should assign the asset to a location")
        elif not self.source_line_ids:
            raise ValidationError('Source line should be added')
        self.write({'state': 'open'})

        if not self.asset_id.category_invisible:
            self.asset_id.write({'category_invisible':True})

        if not self.env['asset_management.transaction'].search([('asset_id','=', self.asset_id.id),('book_id','=', self.book_id.id),('trx_type','=','addition')]):
            if self.book_id.start_date > self.date_in_service:
                raise ValidationError("Date in service dose't belong to fiscal period change either the date in service or the fiscal period" )
            self.env['asset_management.transaction'].create({
                'asset_id': self.asset_id.id,
                'book_id': self.book_id.id,
                'category_id': self.category_id.id,
                'trx_type': 'addition',
                'trx_date': self.book_id.start_date,
                'trx_details': 'New Asset ' + self.asset_id.name + ' Is Added to the Book: ' + self.book_id.name +
                '\n with cost = '+str (self.original_cost)
            })
            for record in self.assignment_id:
                if record.transfer_date:
                    date=record.transfer_date
                else:
                    date='not specified'
                self.env['asset_management.transaction'].create({
                    'book_id': record.book_id.id,
                    'asset_id': record.asset_id.id,
                    'category_id': record.book_assets_id.category_id.id,
                    'trx_type': 'transfer',
                    'trx_date': datetime.today(),
                    'trx_details': 'Responsible : '+ record.responsible_id.name + '\nLocation : '+ record.location_id.name +
                                   '\n on date: '+date if record.responsible_id else 'Location : '+record.location_id.name + '\n on date: '+date
                })

    @api.multi
    def set_to_draft(self):
        self.write({'state': 'draft'})

    @api.depends('assignment_id')
    def _modify_percentage(self):
        for record in self:
            for assignment in record.assignment_id:
                record.percentage += assignment.percentage

    @api.constrains('assignment_id')
    def _checkpercentage(self):
        for record in self:
            # if record.percentage not in (0, 100):
            #     raise ValidationError("Assignment does not add up to 100")
            if float_compare(record.percentage, 100.00, precision_digits=2) != 0:
                raise ValidationError("Assignment does not equal a 100")

    # @api.depends('depreciation_line_ids.move_check','depreciation_line_ids.amount')
    # def _compute_accumulated_value(self):
    #     for record in self:
    #         for line in record.depreciation_line_ids:
    #             if line.move_check:
    #                 record.accumulated_value += line.amount

    @api.one
    @api.depends('current_cost', 'salvage_value','accumulated_value')
                 #'depreciation_line_ids.move_check', 'depreciation_line_ids.amount')
    def _amount_residual(self):
       # total_amount = 0.0
        # for line in self.depreciation_line_ids:
        #     if line.move_check:
        #         total_amount += line.amount
        self.residual_value = self.current_cost - self.accumulated_value - self.salvage_value

    def _compute_board_undone_dotation_nb(self, depreciation_date):
        if self.method_time == 'end':
            if not self.end_date :
                raise ValidationError ('End Date Is Required !')
            end_date = datetime.strptime(self.end_date, DF).date()
            undone_dotation_number = 0
            while depreciation_date <= end_date:
                depreciation_date = date(depreciation_date.year, depreciation_date.month,
                                         depreciation_date.day) + relativedelta(months=+self.life_months)
                undone_dotation_number += 1
        else:
            if self.method_number == 0 :
                raise ValidationError ('Number of Depreciation Should Not be 0 ')
            undone_dotation_number = self.method_number
        return undone_dotation_number

    def _compute_board_amount(self, sequence, residual_amount, amount_to_depr, undone_dotation_number,
                              posted_depreciation_line_ids):
        amount = 0
        if sequence == undone_dotation_number:
            amount = residual_amount
        else:
            if self.method == 'linear':
                amount = amount_to_depr / (undone_dotation_number - len(posted_depreciation_line_ids))
            elif self.method == 'degressive':
                amount = residual_amount * self.method_progress_factor
        return amount

    @api.multi
    def compute_depreciation_board(self):
        self.ensure_one()
        # assign_in_book_asset=self.env['asset_management.assignment'].search([('asset_id','=',self.asset_id.id),('book_id','=',self.book_id.id)])
        if not self.assignment_id:
            raise UserError ("You should assign the asset to a location")
        elif self.date_in_service is  False :
            raise UserError("Date in service must be entered")
        elif not self.source_line_ids:
            raise ValidationError('Source line should be added')

        posted_depreciation_line_ids = self.depreciation_line_ids.filtered(lambda x: x.move_check).sorted(
            key=lambda l: l.depreciation_date)
        unposted_depreciation_line_ids = self.depreciation_line_ids.filtered(lambda x: not x.move_check)

        # Remove old unposted depreciation lines. We cannot use unlink() with One2many field
        commands = [(2, line_id.id, False) for line_id in unposted_depreciation_line_ids]

        if self.residual_value != 0.0:
            amount_to_depr = residual_amount = self.residual_value
            # if self.life_months >= 12:
            #     asset_date = datetime.strptime(self.date_in_service[:4] + '-01-01', DF).date()
            # else:
            asset_date = datetime.strptime(self.date_in_service[:7] + '-01', DF).date()
            # if we already have some previous validated entries, starting date isn't 1st January but last entry + method period
            if posted_depreciation_line_ids and posted_depreciation_line_ids[-1].depreciation_date:
                last_depreciation_date = datetime.strptime(posted_depreciation_line_ids[-1].depreciation_date,
                                                           DF).date()
                depreciation_date = last_depreciation_date + relativedelta(months=+self.life_months)
            else:
                depreciation_date = asset_date

            day = depreciation_date.day
            month = depreciation_date.month
            year = depreciation_date.year


            undone_dotation_number = self._compute_board_undone_dotation_nb(depreciation_date)

            for x in range(len(posted_depreciation_line_ids), undone_dotation_number):
                sequence = x + 1
                amount = self._compute_board_amount(sequence, residual_amount, amount_to_depr, undone_dotation_number,
                                                    posted_depreciation_line_ids)
                currency=self.book_id.company_id.currency_id
                amount = currency.round(amount)
                if float_is_zero(amount, precision_rounding=currency.rounding):
                    continue
                residual_amount -= amount
                vals = {
                    'amount': amount,
                    'asset_id': self.asset_id.id,
                    'book_id': self.book_id.id,
                    'sequence': sequence,
                    'name': (self.name or '') + '/' + str(sequence),
                    'remaining_value': residual_amount,
                    'depreciated_value': self.current_cost - (self.salvage_value + residual_amount),
                    'depreciation_date': depreciation_date.strftime(DF),
                }
                commands.append((0, False, vals))
                # Considering Depr. Period as months
                depreciation_date = date(year, month, day) + relativedelta(months=+self.life_months)
                day = depreciation_date.day
                month = depreciation_date.month
                year = depreciation_date.year
        self.write({'depreciation_line_ids':commands})
        if self.current_cost_from_retir:
            self.current_cost_from_retir = False
        return  True

    # open move.entry form view
    #asset_management.book_assets_list_action
    @api.multi
    def open_entries(self):
        move_ids = []
        for asset in self:
            for depreciation_line in asset.depreciation_line_ids:
                if depreciation_line.move_id:
                    move_ids.append(depreciation_line.move_id.id)
        return {
            'name': _('Journal Entries'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', move_ids)],
        }

    # number of generated entries

    @api.multi
    @api.depends('depreciation_line_ids.move_id')
    def _asset_entry_count(self):
        for asset in self:
            res = self.env['asset_management.depreciation'].search_count(
                [('asset_id', '=', asset.asset_id.id), ('book_id','=',asset.book_id.id),('move_id', '!=', False)])
            asset.entry_count = res or 0


# get default value from CategoryBook
    @api.onchange('book_id')
    def onchange_book_id(self):
        vals = self.onchange_book_id_value(self.book_id.id)
        # We cannot use 'write' on an object that doesn't exist yet
        if vals:
            for k, v in vals['value'].items():
                setattr(self, k, v)


    def onchange_book_id_value(self,book_id):
        if book_id:
            category_book = self.env['asset_management.category_books'].search([('book_id', '=', book_id),('category_id', '=', self._context.get('category_id'))])
            return{
                'value' : {
                'method': category_book.depreciation_method,
                'method_time':category_book.method_time,
                'life_months':category_book.life_months,
                'method_number':category_book.method_number,
                'category_id':category_book.category_id.id
                    }
                }

    # @api.onchange('category_id')
    # def _change_asset_form_category(self):
    #     if self.category_id:
    #         if self.asset_id.category_id.id != self.category_id.id:
    #             # self.asset_id.write({'category_id':self.category_id.id})
    #                self.asset_id.category_id=self.category_id.id


#to hide the depreciation compute button
    @api.depends('depreciation_line_ids')
    def _depreciation_line_length(self):
        for record in self:
            record.depreciation_line_length=len(record.depreciation_line_ids)


#compute percentage for salvage value
    @api.one
    @api.depends('salvage_value_type','salvage_value_amount')
    def _compute_salvage_value(self):
        for record in self:
            if record.salvage_value_type == 'amount':
                record.salvage_value=record.salvage_value_amount
            elif record.salvage_value_type=='percentage':
                record.salvage_value=(record.salvage_value_amount * record.current_cost)/100

    @api.multi
    def move_to_book_asset(self):
        #view_id = self.env.ref('asset_management.book_assets_form_view').id
        return{
                         'type': 'ir.actions.act_window',
                         'name': _(' Asset In Book'),
                         'view_type': 'form',
                         'view_mode': 'form',
                         'res_model': 'asset_management.book_assets',
                         'res_id':self.id,
                         'target': 'current',

           }


class Assignment(models.Model):
    _name = 'asset_management.assignment'
    name = fields.Char(string="Assignment",readonly='True',index=True)
    book_assets_id = fields.Many2one('asset_management.book_assets',on_delete = 'cascade')
    book_id = fields.Many2one("asset_management.book", string="Book",on_delete = 'cascade',compute="_get_book_name")
    asset_id = fields.Many2one("asset_management.asset", string="Asset", on_delete='cascade',compute="_get_asset_name")
    depreciation_expense_account=fields.Many2one('account.account',on_delete='set_null',required=True,domain=[('user_type_id','=','Depreciation')])
    responsible_id = fields.Many2one('hr.employee', on_delete='set_null')
    location_id = fields.Many2one('asset_management.location',required=True,domain=[('active','=',True)])
    is_not_used = fields.Boolean( defult = False )
    # end_use_date = fields.Date()
    transfer_date = fields.Date()
    comments = fields.Text()
    percentage = fields.Float(default=100)

    @api.constrains('percentage')
    def _check_valid_percentage(self):
        for record in self:
             if not  record.percentage < 101.00 and not record.percentage > 0.00:
                raise ValidationError("Invalid value")

#get default value from CategoryBook
    @api.onchange('responsible_id')
    def onchange_responsible_id(self):
        # if not self.book_assets_id:
        #     return

        category_book = self.env['asset_management.category_books'].search(
            [('book_id','=', self.book_id.id), ('category_id','=', self.book_assets_id.category_id.id)])
        value = {
            'depreciation_expense_account':category_book.depreciation_expense_account
        }
        for k, v in value.items():
            setattr(self, k, v)

#creat transaction record when adding a new assignment and location
    @api.model
    def create(self, values):
        values['name']=self.env['ir.sequence'].next_by_code('asset_management.assignment.Assignment')
        record=super(Assignment, self).create(values)
        if record.book_assets_id.state == 'open':
            if record.transfer_date:
                date = record.transfer_date
            else:
                date = 'not specified'
            record.env['asset_management.transaction'].create({
                'book_id':record.book_id.id,
                'asset_id': record.asset_id.id,
                'category_id': record.book_assets_id.category_id.id,
                'trx_type': 'transfer',
                'trx_date': datetime.today(),
                'trx_details':'Responsible : '+ record.responsible_id.name + '\nLocation : '+ record.location_id.name +
                                   '\n on date: '+date if record.responsible_id else 'Location : '+record.location_id.name + '\n on date: '+date
            })
        return record

    @api.depends('book_assets_id')
    def _get_asset_name(self):
        for rec in self:
             rec.asset_id=rec.book_assets_id.asset_id.id
             return rec.asset_id

    @api.depends('book_assets_id')
    def _get_book_name(self):
        for rec in self:
            rec.book_id=rec.book_assets_id.book_id.id
            return rec.book_id

#create transaction when changing responsible or location in capitalize asset
    @api.multi
    def write(self,values):
        old_responsible=self.responsible_id
        if not old_responsible:
            old_responsible = 'None'
        else:
            old_responsible=old_responsible.name
        old_location=self.location_id
        super(Assignment, self).write(values)
        if self.book_assets_id.state == 'open':
            if self.transfer_date:
                date = self.transfer_date
            else:
                date = 'not specified'
            if 'responsible_id' in values:
                if  self.responsible_id != old_responsible :
                    self.env['asset_management.transaction'].create({
                        'asset_id':self.asset_id.id,
                        'book_id':self.book_id.id,
                        'category_id':self.book_assets_id.category_id.id,
                        'trx_type':'transfer',
                        'trx_date':datetime.today(),
                        'trx_details':'Old Responsible : '+old_responsible+'\nNew Responsible : '+self.responsible_id.name
                                            +'\ on date: ' + date
                                                                    })
            if 'location_id' in values:
                if self.location_id != old_location :
                    self.env['asset_management.transaction'].create({
                        'asset_id': self.asset_id.id,
                        'book_id':self.book_id.id,
                        'category_id': self.book_assets_id.category_id.id,
                        'trx_type': 'transfer',
                        'trx_date': datetime.today(),
                        'trx_details': 'Old Location : '+old_location.name+'\nNew Location : '+self.location_id.name
                                                +'\ on date: ' +date
                    })


class SourceLine(models.Model):
    _name = 'asset_management.source_line'
    name = fields.Char(string="Source Line Number",readonly=True,index=True)
    book_assets_id = fields.Many2one('asset_management.book_assets', on_delete='cascade')
    asset_id = fields.Many2one('asset_management.asset',on_delete = 'cascade',compute='_get_asset_name')
    book_id=fields.Many2one('asset_management.book',on_delete='cascade',compute='_get_book_name')
    source_type = fields.Selection(
        [('invoice','Invoice'),('null','Null')
        ],default='invoice',required=True
    )
    invoice_id = fields.Many2one("account.invoice", string="invoice",on_delete='cascade')
    invoice_line_ids = fields.Many2one("account.invoice.line", string="Invoice Line",on_delete='cascade')
    amount = fields.Float('Amount',compute="_get_price_from_invoice")
    description = fields.Text()

    @api.model
    def create(self, values):
        values['name']=self.env['ir.sequence'].next_by_code('asset_management.source_line.SourceLine')
        return super(SourceLine, self).create(values)

    @api.onchange('invoice_id')
    def _onchange_invoice_id(self):
        if self.invoice_id:
            invoice_line=[]
            for line in self.invoice_id.invoice_line_ids:
                invoice_line.append(line.id)
            return{'domain':{'invoice_line_ids':[('id','in',invoice_line)]
            }}

    @api.one
    @api.depends('invoice_id','invoice_line_ids')
    def _get_price_from_invoice(self):
        for record in self:
            record.amount=record.invoice_line_ids.price_unit

    @api.depends('book_assets_id')
    def _get_asset_name(self):
        for rec in self:
            rec.asset_id=rec.book_assets_id.asset_id.id
            return rec.asset_id

    @api.depends('book_assets_id')
    def _get_book_name(self):
        for rec in self:
            rec.book_id=rec.book_assets_id.book_id.id
            return rec.book_id


class Depreciation(models.Model):
    _name = 'asset_management.depreciation'
    name = fields.Char(string="Depreciation Number",readonly=True,index=True)
    book_assets_id = fields.Many2one('asset_management.book_assets', on_delete='cascade')
    asset_id = fields.Many2one('asset_management.asset', on_delete='cascade')
    book_id = fields.Many2one('asset_management.book', on_delete='cascade')
    sequence = fields.Integer(required=True)
    amount = fields.Float(string='Current Depreciation', digits=0, )
    remaining_value = fields.Float(string='Next Period Depreciation', digits=0, required=True)
    depreciated_value = fields.Float(string='Cumulative Depreciation', required=True)
    depreciation_date = fields.Date('Depreciation Date', index=True)
    move_id = fields.Many2one('account.move', string='Depreciation Entry')
    move_check = fields.Boolean(compute='_get_move_check', string='Linked (Account)', track_visibility='always', store=True)
    move_posted_check = fields.Boolean(compute='_get_move_posted_check', string='Posted', track_visibility='always',store=True)
    parent_state = fields.Selection(related="book_assets_id.state", string='State of Asset')

    @api.multi
    @api.depends('move_id')
    def _get_move_check(self):
        for line in self:
            #line.book_assets_id.accumulated_value = line.depreciated_value
            line.move_check = bool(line.move_id)

    @api.multi
    @api.depends('move_id.state')
    def _get_move_posted_check(self):
        for line in self:
            line.move_posted_check = True if line.move_id and line.move_id.state == 'posted' else False

# generate entries in account.move
    @api.multi
    def create_move(self, post_move=True):
        created_moves = self.env['account.move']
        prec = self.env['decimal.precision'].precision_get('Account')
        # current_currency = self.env['res.company'].search([('id','=',1)])[0].currency_id
        journal_id=self.env['asset_management.category_books'].search([('book_id', '=', self.book_id.id),('category_id', '=', self.book_assets_id.category_id.id)]).journal_id
        for line in self:
            if line.move_id:
                raise UserError(
                    _('This depreciation is already linked to a journal entry! Please post or delete it.'))
            company_currency=line.book_id.company_id.currency_id
            current_currency=line.asset_id.currency_id
            depreciation_date = self.env.context.get('depreciation_date') or line.depreciation_date or fields.Date.context_today(self)
            accumulated_depreciation_account = line.env['asset_management.category_books'].search( [('book_id', '=', self.book_id.id), ('category_id', '=',self.book_assets_id.category_id.id)])[0].accumulated_depreciation_account
            #depreciation_expense_account=line.env['asset_management.assignment'].search([('asset_id','=',self.asset_id.id),('book_id','=',self.book_id.id)]).depreciation_expense_account
            partner_id=line.env['asset_management.source_line'].search([('asset_id','=',self.asset_id.id)])[0].invoice_id.partner_id
            if partner_id is None:
                raise ValidationError ("Source Line must be entered")
            asset_name = line.asset_id.name + ' (%s/%s)' % (line.sequence, len(line.asset_id.depreciation_line_ids))
            amount = current_currency.with_context(date=depreciation_date).compute(line.amount, company_currency)
            move_line_1 = {
                'name': asset_name,
                'account_id':accumulated_depreciation_account.id,
                'debit': 0.0 if float_compare(amount, 0.0, precision_digits=prec) > 0 else -amount,
                'credit': amount if float_compare(amount, 0.0, precision_digits=prec) > 0 else 0.0,
                'journal_id':journal_id.id,
                'partner_id': partner_id.id,
                'analytic_account_id': False,
                'currency_id': company_currency != current_currency and current_currency.id or False,
                'amount_currency': company_currency != current_currency and - 1.0 * line.amount or 0.0,
            }
            move_vals = {
            'ref': line.asset_id.name,
            'date': depreciation_date or False,
            'journal_id': journal_id.id,
            'line_ids': [(0, 0, move_line_1)],
            }
            assignment_in_book=line.env['asset_management.assignment'].search([('book_assets_id','=',line.book_assets_id.id)])
            for assignment in assignment_in_book:
                amount=(line.amount * assignment.percentage)/100.00
                # amount = current_currency.with_context(date=depreciation_date).compute(amount,company_currency)
                depreciation_expense_account=assignment.depreciation_expense_account.id
                move_line_2 = {
                    'name': asset_name,
                    'account_id': depreciation_expense_account,
                    'credit': 0.0 if float_compare(amount, 0.0, precision_digits=prec) > 0 else -amount,
                    'debit': amount if float_compare(amount, 0.0, precision_digits=prec) > 0 else 0.0,
                    'journal_id': journal_id.id,
                    'partner_id': partner_id.id,
                    'analytic_account_id': False,
                    'currency_id': company_currency != current_currency and current_currency.id or False,
                    'amount_currency': company_currency != current_currency and - 1.0 * line.amount or 0.0,
                    }
                move_vals['line_ids'].append((0, 0, move_line_2))
            move = self.env['account.move'].create(move_vals)
            line.write({'move_id': move.id, 'move_check': True})
            line.book_assets_id.accumulated_value = line.depreciated_value
            created_moves |= move
            #source_line=self.env['asset_management.source_line'].search([('asset_id','=',self.asset_id.id),('source_type','=','invoice')])
            # if post_move and created_moves:
            #     created_moves.filtered(
            #         lambda m: any(m.asset_depreciation_id.mapped('asset_id.source_line_id'))).post()
            return [x.id for x in created_moves]

    @api.multi
    def post_lines_and_close_asset(self):
        # we re-evaluate the assets to determine whether we can close them
        for line in self:
            # line.log_message_when_posted()
            asset = line.asset_id
            book=line.book_id
            book_asset=line.env['asset_management.book_assets'].search([('asset_id','=',asset.id),('book_id','=',book.id)])
            residual_value=book_asset[0].residual_value
            current_currency = self.env['res.company'].search([('id', '=', 1)])[0].currency_id
            if current_currency.is_zero(residual_value):
                #asset.message_post(body=_("Document closed."))
                book_asset.write({'state': 'close'})

    @api.multi
    def unlink(self):
        for record in self:
            if record.move_check:
                if record.asset_id.source_line_id.source_type == 'po':
                    msg = _("You cannot delete posted depreciation lines.")
                else:
                    msg = _("You cannot delete posted installment lines.")
                raise UserError(msg)
        return super(Depreciation, self).unlink()

    @api.model
    def create(self, values):
        values['name'] = self.env['ir.sequence'].next_by_code('asset_management.depreciation.Depreciation')
        return super(Depreciation,self).create(values)


class Retirement (models.Model):
    _name = 'asset_management.retirement'
    name=fields.Char(string="Retirement Number",readonly=True,index=True)
    book_assets_id = fields.Many2one('asset_management.book_assets',on_delete = 'cascade',compute="_get_book_assets_id")
    book_id=fields.Many2one('asset_management.book',on_delete = 'cascade',required=True,domain=[('active','=',True)])
    asset_id = fields.Many2one('asset_management.asset', on_delete='cascade',required=True)
    retire_date = fields.Date(string = 'Retire Date',default=datetime.today())
    comments = fields.Text(string = "Comments")
    gain_loss_amount=fields.Float()
    proceeds_of_sale = fields.Float()
    cost_of_removal= fields.Float()
    partner_id = fields.Many2one(comodel_name="res.partner", string="Sold To")
    check_invoice= fields.Char()
    retired_cost=fields.Float(required=True)
    current_asset_cost=fields.Float(string="Current Cost",readonly=True)
    net_book_value=fields.Float()
    accumulated_value=fields.Float()
    retirement_type_id=fields.Many2one('asset_management.retirement_type',on_delete="set_null")
    prorate_date = fields.Date(string='Prorate Date', compute="_compute_prorate_date")
    state=fields.Selection([('draft','Draft'),('complete','Complete'),('reinstall','Reinstall')],
                           'Status', required = True, copy = False, default = 'draft')

    @api.one
    @api.depends('retire_date')
    def _compute_prorate_date(self):
        for record in self:
            if record.retire_date:
                asset_date = datetime.strptime(record.retire_date[:7] + '-01', DF).date()
                record.prorate_date=asset_date

    @api.constrains('retire_date')
    def _retire_date_check(self):
        if self.retire_date > self.book_id.end_date or self.retire_date < self.book_id.start_date :
            raise ValidationError("Retirement date must be in fiscal period from " + self.book_id.start_date+ " to " +self.book_id.end_date+
                                  "\nchange the date in service or the fiscal period")

    @api.onchange('book_id')
    def _asset_in_book(self):
        if self.book_id:
            res=[]
            asset_in_book=self.env['asset_management.book_assets'].search([('book_id','=',self.book_id.id)])
            for asset in asset_in_book:
                if asset.state == 'open':
                    res.append(asset.asset_id.id)

            return {'domain':{'asset_id':[('id','in',res)]
                                  } }

    @api.depends('book_id','asset_id')
    def _get_book_assets_id(self):
        for record in self:
            if record.book_id and record.asset_id:
                asset_book=record.env['asset_management.book_assets'].search([('asset_id','=',record.asset_id.id),('book_id','=',record.book_id.id)])
                record.book_assets_id=asset_book.id

    # @api.depends('book_id', 'asset_id')
    # def _get_asset_cost(self):
    #     for record in self:
    #         if not record.test:
    #             if record.book_id and record.asset_id:
    #                 asset_gross_value=record.env['asset_management.book_assets'].search([('asset_id','=',record.asset_id.id),('book_id','=',record.book_id.id)]).current_cost
    #                 record.current_asset_cost=asset_gross_value
    #                 record.test= True

    @api.onchange('book_id','asset_id')
    def _get_asset_cost(self):
        self.test =False
        if self.book_id and self.asset_id:
            values = self.get_values_from_book_asset(self.book_id.id,self.asset_id.id)
            if values:
                for k,v in values['value'].items():
                    setattr(self,k,v)


    def get_values_from_book_asset(self,book_id,asset_id):
        if book_id and asset_id:
            asset_value = self.env['asset_management.book_assets'].search(
                [('asset_id', '=', self.asset_id.id), ('book_id', '=', self.book_id.id)])
            return {'value':
                        {'current_asset_cost':asset_value.current_cost,
                         'accumulated_value':asset_value.accumulated_value,
                         'net_book_value':asset_value.net_book_value}
                    }

    @api.onchange('retired_cost','current_asset_cost')
    def _compute_gain_lost(self):
        if self.retired_cost and self.current_asset_cost:
            self.gain_loss_amount = self.retired_cost - self.accumulated_value


    @api.multi
    def required_computation(self):
        for record in self:
            if record.retired_cost == 0 :
                raise ValidationError('Retired cost must be entered.')
            current_cost=record.book_assets_id.current_cost
            record.gain_loss_amount = record.retired_cost - record.accumulated_value
            if record.retired_cost <= record.accumulated_value :
                net_book = (current_cost - record.retired_cost) - (record.accumulated_value - record.retired_cost)
            elif record.retired_cost > record.accumulated_value or record.retired_cost == current_cost:
                net_book = current_cost - record.retired_cost
            record.current_asset_cost=current_cost
            record.book_assets_id.write({'current_cost':net_book,
                                         'current_cost_from_retir':True,
                                         'accumulated_value':0.0})
            record.book_assets_id.compute_depreciation_board()

    @api.multi
    def reinstall(self):
        trx=self.env['asset_management.transaction'].search([('retirement_id','=',self.id)])
        journal_entries=trx.move_id
        journal_id=journal_entries.journal_id
        date=datetime.today()
        reserved_jl=self.env['account.move'].browse(journal_entries.id).reverse_moves(date,journal_id)
        if reserved_jl:
            self.state = 'reinstall'
            return {
                'name':_('Reinstall move'),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'res_model': 'account.move',
                'domain': [('id', 'in', reserved_jl)],
            }


    @api.model
    def create(self, values):
        values['name'] = self.env['ir.sequence'].next_by_code('asset_management.retirement.Retirement')
        res=super(Retirement,self).create(values)
        res.required_computation()
        if res.retired_cost == res.current_asset_cost:
            res.env['asset_management.transaction'].create({
                'asset_id': res.asset_id.id,
                'book_id': res.book_id.id,
                'category_id': res.book_assets_id.category_id.id,
                'trx_type': 'full_retirement',
                'trx_date': res.retire_date,
                'retirement_id':res.id,
                'trx_details': 'A full retirement has occur for asset (' + str(res.asset_id.name) + ') on book (' + str(
                    res.book_id.name) + ')'
            })
        else :
            res.env['asset_management.transaction'].create({
                'asset_id':res.asset_id.id,
                'book_id':res.book_id.id,
                'category_id':res.book_assets_id.category_id.id,
                'trx_type':'partial_retirement',
                'trx_date':res.retire_date,
                'retirement_id': res.id,
                'trx_details':'A partial retirement has occur for asset ('+str(res.asset_id.name)+') on book ('+str(res.book_id.name)+')'

            })
        return res


class CategoryBooks(models.Model):
    _name= 'asset_management.category_books'
    name = fields.Char(string="Category Books Num",index=True)
    category_id = fields.Many2one('asset_management.category',readonly=True,on_delete='cascade',string='Category')
    book_id = fields.Many2one('asset_management.book',on_delete='cascade',string='Book Num',required=True,domain=[('active','=',True)])
    asset_cost_account = fields.Many2one('account.account',on_delete='set_null',required=True,domain=[('user_type_id','=','Fixed Assets')])
    asset_clearing_account = fields.Many2one('account.account', on_delete='set_null',required=True,domain=[('user_type_id','=','Fixed Assets')])
    depreciation_expense_account = fields.Many2one('account.account', on_delete='set_null',required=True,domain=[('user_type_id','=','Depreciation')])
    accumulated_depreciation_account = fields.Many2one('account.account', on_delete='set_null',required=True,domain=[('user_type_id','=','Fixed Assets')])
    book_with_cate=fields.Boolean(related='book_id.book_with_cate')
    group_entries=fields.Boolean(deafult=True)
    journal_id = fields.Many2one('account.journal', string='Journal', required=True)
    depreciation_method = fields.Selection([('linear','Linear'),('degressive','Degressive')],default='linear')
    life_months = fields.Integer(required=True)
    method_time = fields.Selection([('number', 'Number of Entries'), ('end', 'Ending Date')], string='Time Method',required=True,default='number',
                                   help="Choose the method to use to compute the dates and number of entries.\n"
                                        "  * Number of Entries: Fix the number of entries and the time between 2 depreciations.\n"
                                        "  * Ending Date: Choose the time between 2 depreciations and the date the depreciations won't go beyond.")
    method_number=fields.Integer(string='Number of Depreciation',help="The number of depreciations needed to depreciate your asset")
    _sql_constraints=[
        ('unique_book_id_on_cat', 'UNIQUE(book_id,category_id)', 'Category is already added to this book..!')
    ]


    @api.model
    def create(self, values):
        values['name'] = self.env['ir.sequence'].next_by_code('asset_management.category_books.CategoryBooks')
        return super(CategoryBooks, self).create(values)


    @api.onchange('book_id')
    def onchange_book_id(self):
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
            ('cost_adjustment','Cost Adjustment'),
            ('full_retirement','Full Retirement'),
            ('partial_retirement','Partial Retirement')
        ]
    )
    trx_date = fields.Date('Transaction Date')
    trx_details = fields.Text('Transaction Details')
    old_category=fields.Many2one("asset_management.category", string="Category",on_delete='cascade')
    move_id = fields.Many2one('account.move', string='Transaction Entry')
    move_check = fields.Boolean(compute='_get_move_check', string='Linked (Account)', track_visibility='always', store=True)
    move_posted_check = fields.Boolean(compute='_get_move_posted_check', string='Posted', track_visibility='always',store=True)
    cost=fields.Float()
    retirement_id=fields.Many2one('asset_management.retirement')

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

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('asset_management.transaction.Transaction')
        record=super(Transaction, self).create(vals)
        return record

    @api.multi
    def create_trx_move(self):
        prec = self.env['decimal.precision'].precision_get('Account')
        created_moves = self.env['account.move']
        for line in self:
            trx_name = line.name
            current_currency = line.asset_id.currency_id
            company_currency = line.book_id.company_id.currency_id
            gross_value = line.env['asset_management.book_assets'].search(
                [('asset_id', '=', line.asset_id.id), ('book_id', '=', line.book_id.id)]).current_cost
            if line.trx_type == 'addition':
                # journal_id = self.env['asset_management.category_books'].search(
                #     [('book_id', '=', self.book_id.id), ('category_id', '=', self.category_id.id)]).journal_id
                accounts=line.env['asset_management.category_books'].search([('book_id','=',line.book_id.id),('category_id','=',line.category_id.id)])
                journal_id=accounts.journal_id
                asset_cost_account=accounts.asset_cost_account.id
                asset_clearing_account=accounts.asset_clearing_account.id
                #credit
                move_line_1 = {
                    'name': trx_name,
                    'account_id':asset_clearing_account,
                    'debit': 0.00 if float_compare(gross_value, 0.0, precision_digits=prec) > 0 else -gross_value,
                    'credit':gross_value if float_compare(gross_value, 0.0, precision_digits=prec) > 0 else 0.0,
                    'journal_id':journal_id.id,
                    'analytic_account_id': False,
                    'currency_id': company_currency != current_currency and current_currency.id or False,
                    'amount_currency': company_currency != current_currency and - 1.0 * 50 or 0.0,
                }
                #debit
                move_line_2 = {
                    'name': trx_name,
                    'account_id': asset_cost_account,
                    'credit':0.00 if float_compare(gross_value, 0.0, precision_digits=prec) > 0 else -gross_value ,
                    'debit':gross_value if float_compare(gross_value, 0.0, precision_digits=prec) > 0 else 0.0,
                    'journal_id': journal_id.id,
                    'analytic_account_id': False,
                    'currency_id': company_currency != current_currency and current_currency.id or False,
                    'amount_currency': company_currency != current_currency and - 1.0 * 50 or 0.0,
                }

                move_vals = {
                'ref': line.asset_id.name,
                'date': datetime.today() or False,
                'journal_id': journal_id.id,
                'line_ids': [(0, 0, move_line_1),(0,0,move_line_2)],
                }
                move = line.env['account.move'].create(move_vals)
                line.write({'move_id': move.id, 'move_check': True})
                created_moves |= move

            elif line.trx_type == 're_class':
                old_accounts=line.env['asset_management.category_books'].search([('category_id','=',line.old_category.id),('book_id','=',line.book_id.id)])
                new_accounts=line.env['asset_management.category_books'].search([('category_id','=',line.category_id.id),('book_id','=',line.book_id.id)])
                old_asset_cost_account=old_accounts.asset_cost_account.id
                new_asset_cost_account=new_accounts.asset_cost_account.id
                old_accumulated_depreciation_account=old_accounts.accumulated_depreciation_account.id
                new_accumulated_depreciation_account=new_accounts.accumulated_depreciation_account.id
                journal_id=new_accounts.journal_id
                # date=datetime.strptime(line.trx_date[:7]+'-01',DF).date()
                acc_value=line.env['asset_management.book_assets'].search([('asset_id','=',line.asset_id.id),('book_id','=',line.book_id.id)]).accumulated_value
                # dep_value=0
                # for value in depreciated_value:
                #     dep_value +=value.depreciated_value

                # credit
                move_line_1 = {
                    'name': trx_name,
                    'account_id': old_asset_cost_account,
                    'debit': 0.00 if float_compare(gross_value, 0.0, precision_digits=prec) > 0 else -gross_value,
                    'credit': gross_value if float_compare(gross_value, 0.0, precision_digits=prec) > 0 else 0.0,
                    'journal_id': journal_id.id,
                    'analytic_account_id': False,
                    'currency_id': company_currency != current_currency and current_currency.id or False,
                    'amount_currency': company_currency != current_currency and - 1.0 * 50 or 0.0,
                }
                # debit
                move_line_2 = {
                    'name': trx_name,
                    'account_id': new_asset_cost_account,
                    'credit': 0.00 if float_compare(gross_value, 0.0, precision_digits=prec) > 0 else -gross_value,
                    'debit': gross_value if float_compare(gross_value, 0.0, precision_digits=prec) > 0 else 0.0,
                    'journal_id': journal_id.id,
                    'analytic_account_id': False,
                    'currency_id': company_currency != current_currency and current_currency.id or False,
                    'amount_currency': company_currency != current_currency and - 1.0 * 50 or 0.0,
                }

                #credit
                move_line_3 = {
                    'name': trx_name,
                    'account_id': new_accumulated_depreciation_account,
                    'debit': 0.00 if float_compare(acc_value, 0.0, precision_digits=prec) > 0 else -acc_value,
                    'credit': acc_value if float_compare(acc_value, 0.0, precision_digits=prec) > 0 else 0.0,
                    'journal_id': journal_id.id,
                    'analytic_account_id': False,
                    'currency_id': company_currency != current_currency and current_currency.id or False,
                    'amount_currency': company_currency != current_currency and - 1.0 * 50 or 0.0,
                }
                # debit
                move_line_4 = {
                    'name': trx_name,
                    'account_id': old_accumulated_depreciation_account,
                    'credit': 0.00 if float_compare(acc_value, 0.0, precision_digits=prec) > 0 else -acc_value,
                    'debit': acc_value if float_compare(acc_value, 0.0, precision_digits=prec) > 0 else 0.0,
                    'journal_id': journal_id.id,
                    'analytic_account_id': False,
                    'currency_id': company_currency != current_currency and current_currency.id or False,
                    'amount_currency': company_currency != current_currency and - 1.0 * 50 or 0.0,
                }

                move_vals = {
                    'ref': self.asset_id.name,
                    'date': datetime.today() or False,
                    'journal_id': journal_id.id,
                    'line_ids': [(0, 0, move_line_1), (0, 0, move_line_2),(0,0,move_line_3),(0,0,move_line_4)],
                }
                move = line.env['account.move'].create(move_vals)
                line.write({'move_id': move.id, 'move_check': True})
                created_moves |= move

            elif line.trx_type == 'cost_adjustment':
                accounts = line.env['asset_management.category_books'].search(
                    [('book_id', '=', line.book_id.id), ('category_id', '=', line.category_id.id)])
                journal_id = accounts.journal_id
                asset_cost_account = accounts.asset_cost_account.id
                asset_clearing_account = accounts.asset_clearing_account.id
                # credit
                move_line_1 = {
                    'name': trx_name,
                    'account_id': asset_clearing_account,
                    'debit': 0.00 if float_compare(line.cost, 0.0, precision_digits=prec) > 0 else -line.cost,
                    'credit': line.cost if float_compare(line.cost, 0.0, precision_digits=prec) > 0 else 0.0,
                    'journal_id': journal_id.id,
                    'analytic_account_id': False,
                    'currency_id': company_currency != current_currency and current_currency.id or False,
                    'amount_currency': company_currency != current_currency and - 1.0 * 50 or 0.0,
                }
                # debit
                move_line_2 = {
                    'name': trx_name,
                    'account_id': asset_cost_account,
                    'credit': 0.00 if float_compare(line.cost, 0.0, precision_digits=prec) > 0 else -line.cost,
                    'debit': line.cost if float_compare(line.cost, 0.0, precision_digits=prec) > 0 else 0.0,
                    'journal_id': journal_id.id,
                    'analytic_account_id': False,
                    'currency_id': company_currency != current_currency and current_currency.id or False,
                    'amount_currency': company_currency != current_currency and - 1.0 * 50 or 0.0,
                }

                move_vals = {
                    'ref': line.asset_id.name,
                    'date': datetime.today() or False,
                    'journal_id': journal_id.id,
                    'line_ids': [(0, 0, move_line_1), (0, 0, move_line_2)],
                }
                move = line.env['account.move'].create(move_vals)
                line.write({'move_id': move.id, 'move_check': True})
                created_moves |= move

        return [x.id for x in created_moves]

    @api.multi
    def generate_retirement_journal(self):
        created_moves = self.env['account.move']
        prec = self.env['decimal.precision'].precision_get('Account')
        asset_name = self.asset_id.name
        category_books = self.env['asset_management.category_books'].search([('book_id', '=', self.book_id.id), (
        'category_id', '=', self.category_id.id)])
        for trx in self:
            current_currency = trx.asset_id.currency_id
            company_currency = trx.book_id.company_id.currency_id
            # date = datetime.strptime(trx.trx_date[:7] + '-01', DF).date()
            retirement = trx.retirement_id
            accum_value=retirement.accumulated_value
            # depreciated_value = trx.env['asset_management.depreciation'].search(
            #     [('asset_id', '=', trx.asset_id.id), ('book_id', '=', trx.book_id.id),
            #      ('depreciation_date', '<=', date),('move_posted_check','=',True)])
            # accum_value = 0
            # for value in depreciated_value:
            #     accum_value += value.depreciated_value
            cr=0
            db=0
            if retirement.proceeds_of_sale or retirement.cost_of_removal:
                asset_cost_account = category_books.asset_cost_account.id
                accumulated_depreciation_account = category_books.accumulated_depreciation_account.id
                move_line_1 = {
                    'name': asset_name,
                    'account_id': asset_cost_account,
                    'debit': 0.0,
                    'credit': retirement.current_asset_cost,
                    'journal_id': category_books.journal_id.id,
                    'analytic_account_id': False,
                    'currency_id': company_currency != current_currency and current_currency.id or False,
                    'amount_currency': company_currency != current_currency and - 1.0 * retirement.current_asset_cost or 0.0,
                }
                move_vals = {
                    'ref': trx.asset_id.name,
                    'date': trx.trx_date or False,
                    'journal_id': category_books.journal_id.id,
                    'line_ids': [(0, 0, move_line_1)],
                }
                if accum_value:
                    move_line_2 = {
                        'name': asset_name,
                        'account_id': accumulated_depreciation_account,
                        'credit': 0.0,
                        'debit': accum_value,
                        'journal_id': category_books.journal_id.id,
                        'analytic_account_id': False,
                        'currency_id': company_currency != current_currency and current_currency.id or False,
                        'amount_currency': company_currency != current_currency and - 1.0 * accum_value or 0.0,
                     }
                    move_vals['line_ids'].append([0,0,move_line_2])
                    cr += move_line_2['credit']
                    db += move_line_2['debit']
                cr += move_line_1['credit']
                db += move_line_1['debit']

                if retirement.proceeds_of_sale:
                    proceeds_of_sale_account = retirement.retirement_type_id.proceeds_of_sale_account.id
                    move_line_3 = {
                        'name': asset_name,
                        'account_id': proceeds_of_sale_account,
                        'credit': 0.0,
                        'debit': retirement.proceeds_of_sale,
                        'journal_id': category_books.journal_id.id,
                        'analytic_account_id': False,
                        'currency_id': company_currency != current_currency and current_currency.id or False,
                        'amount_currency': company_currency != current_currency and - 1.0 * retirement.proceeds_of_sale or 0.0,
                    }
                    move_vals['line_ids'].append((0, 0, move_line_3))
                    cr += move_line_3['credit']
                    db += move_line_3['debit']

                if retirement.cost_of_removal:
                    cost_of_removal_account = retirement.retirement_type_id.cost_of_removal_account.id
                    move_line_4 = {
                        'name': asset_name,
                        'account_id': cost_of_removal_account,
                        'debit': 0.0,
                        'credit': retirement.cost_of_removal,
                        'journal_id': category_books.journal_id.id,
                        'analytic_account_id': False,
                        'currency_id': company_currency != current_currency and current_currency.id or False,
                        'amount_currency': company_currency != current_currency and - 1.0 * retirement.cost_of_removal or 0.0,
                    }
                    move_vals['line_ids'].append((0, 0, move_line_4))
                    cr += move_line_4['credit']
                    db += move_line_4['debit']

                if db > cr:
                    cost_of_removal_gain_account = retirement.book_id.cost_of_removal_gain_account.id
                    move_line_5 = {
                        'name': asset_name,
                        'account_id': cost_of_removal_gain_account,
                        'debit': 0.0,
                        'credit': db - cr,
                        'journal_id': category_books.journal_id.id,
                        'analytic_account_id': False,
                        'currency_id': company_currency != current_currency and current_currency.id or False,
                        'amount_currency': company_currency != current_currency and - 1.0 * db - cr or 0.0,
                    }
                    move_vals['line_ids'].append((0, 0, move_line_5))
                elif db < cr:
                    cost_of_removal_loss_account = retirement.book_id.cost_of_removal_loss_account.id
                    move_line_5 = {
                        'name': asset_name,
                        'account_id': cost_of_removal_loss_account,
                        'credit': 0.0,
                        'debit': cr - db,
                        'journal_id': category_books.journal_id.id,
                        'analytic_account_id': False,
                        'currency_id': company_currency != current_currency and current_currency.id or False,
                        'amount_currency': company_currency != current_currency and - 1.0 * db - cr or 0.0,
                    }
                    move_vals['line_ids'].append((0, 0, move_line_5))
                # move1 = trx.env['account.move'].create(move_vals1)
            elif self.trx_type == 'partial_retirement' and retirement.retired_cost <= accum_value:
                asset_cost_account=category_books.asset_cost_account.id
                accumulated_depreciation_account=category_books.accumulated_depreciation_account.id
                #credit
                move_line_1 = {
                    'name': asset_name,
                    'account_id': asset_cost_account,
                    'debit': 0.0 if float_compare(retirement.retired_cost, 0.0, precision_digits=prec) > 0 else -retirement.retired_cost,
                    'credit': retirement.retired_cost if float_compare(retirement.retired_cost, 0.0, precision_digits=prec) > 0 else 0.0,
                    'journal_id': category_books.journal_id.id,
                    'analytic_account_id': False,
                    'currency_id': company_currency != current_currency and current_currency.id or False,
                    'amount_currency': company_currency != current_currency and - 1.0 * retirement.retired_cost or 0.0,
                }

                #debit
                move_line_2 = {
                    'name': asset_name,
                    'account_id': accumulated_depreciation_account,
                    'credit': 0.0 if float_compare(retirement.retired_cost, 0.0, precision_digits=prec) > 0 else -retirement.retired_cost,
                    'debit': retirement.retired_cost if float_compare(retirement.retired_cost, 0.0, precision_digits=prec) > 0 else 0.0,
                    'journal_id': category_books.journal_id.id,
                    'analytic_account_id': False,
                    'currency_id': company_currency != current_currency and current_currency.id or False,
                    'amount_currency': company_currency != current_currency and - 1.0 * retirement.retired_cost or 0.0,
                    }
                move_vals = {
                    'ref': trx.asset_id.name,
                    'date': trx.trx_date or False,
                    'journal_id': category_books.journal_id.id,
                    'line_ids': [(0, 0, move_line_1), (0, 0, move_line_2)],
                }
            else :
                asset_cost_account = category_books.asset_cost_account.id
                accumulated_depreciation_account = category_books.accumulated_depreciation_account.id
                cost_of_removal_loss_account=trx.book_id.cost_of_removal_loss_account.id
                # credit
                move_line_1 = {
                    'name': asset_name,
                    'account_id': asset_cost_account,
                    'debit': 0.0 if float_compare(retirement.retired_cost, 0.0,
                                                  precision_digits=prec) > 0 else -retirement.retired_cost,
                    'credit': retirement.retired_cost if float_compare(retirement.retired_cost, 0.0,
                                                                       precision_digits=prec) > 0 else 0.0,
                    'journal_id': category_books.journal_id.id,
                    'analytic_account_id': False,
                    'currency_id': company_currency != current_currency and current_currency.id or False,
                    'amount_currency': company_currency != current_currency and - 1.0 * retirement.retired_cost or 0.0,
                }
                # debit
                debit_amount= retirement.retired_cost - accum_value
                move_line_3 = {
                    'name': asset_name,
                    'account_id': cost_of_removal_loss_account,
                    'credit': 0.0 if float_compare(debit_amount, 0.0,
                                                   precision_digits=prec) > 0 else -debit_amount,
                    'debit': debit_amount if float_compare(debit_amount, 0.0,
                                                                      precision_digits=prec) > 0 else 0.0,
                    'journal_id': category_books.journal_id.id,
                    'analytic_account_id': False,
                    'currency_id': company_currency != current_currency and current_currency.id or False,
                    'amount_currency': company_currency != current_currency and - 1.0 * debit_amount or 0.0,
                }

                move_vals = {
                    'ref': trx.asset_id.name,
                    'date': trx.trx_date or False,
                    'journal_id': category_books.journal_id.id,
                    'line_ids': [(0, 0, move_line_1),(0,0,move_line_3)],
                }
                # debit
                if accum_value:
                    move_line_2 = {
                        'name': asset_name,
                        'account_id': accumulated_depreciation_account,
                        'credit': 0.0 if float_compare(accum_value, 0.0,
                                                       precision_digits=prec) > 0 else -accum_value,
                        'debit': accum_value if float_compare(accum_value, 0.0,
                                                                          precision_digits=prec) > 0 else 0.0,
                        'journal_id': category_books.journal_id.id,
                        'analytic_account_id': False,
                        'currency_id': company_currency != current_currency and current_currency.id or False,
                        'amount_currency': company_currency != current_currency and - 1.0 * accum_value or 0.0,
                    }
                    move_vals['line_ids'].append((0, 0, move_line_2))
            move = trx.env['account.move'].create(move_vals)
            trx.write({'move_id': move.id, 'move_check': True})
            retirement.write({'state':'complete'})
            created_moves |= move
        return [x.id for x in created_moves]


class AssetTag(models.Model):
    _name = 'asset_management.tag'
    name = fields.Char()


class AssetLocation(models.Model):
    _name = 'asset_management.location'
    name = fields.Char()
    city=fields.Char(required=True)
    state_id=fields.Many2one('res.country.state')
    country_id=fields.Many2one('res.country',required=True)
    active=fields.Boolean(default=True)


class RetirementType(models.Model):
    _name='asset_management.retirement_type'
    name=fields.Char(required=True)
    proceeds_of_sale_account=fields.Many2one('account.account',on_delete='set_null',required=True)
    cost_of_removal_account = fields.Many2one('account.account', on_delete='set_null',required=True)


