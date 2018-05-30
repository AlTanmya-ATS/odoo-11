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
    #units = fields.Integer("Units")
    ownership_type = fields.Selection(selection=[('owned', 'Owned')], default='owned')
    is_new = fields.Selection(selection=[('new', 'New')
        , ('used', 'Used')])
    is_in_physical_inventory = fields.Boolean()
    in_use_flag = fields.Boolean()
    parent_asset = fields.Many2one('asset_management.asset', on_delete='cascade')
    item_id = fields.Many2one('product.product', on_delete='set_null')
    category_id = fields.Many2one('asset_management.category', required=True,domain=[('active','=',True)])
    book_assets_id = fields.One2many(comodel_name="asset_management.book_assets", inverse_name="asset_id", string="Book",on_delete='cascade')
    depreciation_line_ids = fields.One2many(comodel_name="asset_management.depreciation", inverse_name="asset_id", string="depreciation",on_delete='cascade')
    asset_serial_number = fields.Char(string ='Serial Number' )
    asset_tag_number = fields.Many2many('asset_management.tag')
    color = fields.Integer('Color Index', default=10)
    #percentage = fields.Float(compute='_modify_percentage')
    # assignment_id = fields.One2many('asset_management.assignment', inverse_name='asset_id')
    _sql_constraints=[
        ('asset_serial_number','UNIQUE(asset_serial_number)','Serial Number already exists!')
    ]
    asset_with_category=fields.Boolean(related='category_id.asset_with_category')
    source_line_id=fields.One2many('asset_management.source_line',string='Source Line',inverse_name='asset_id',on_delete='cascade')
    # default_book=fields.Many2one('asset_management.book',required=True)
    state=fields.Selection([('draft','Draft'),('capitalize','Capitalize'),('retired','Retired')] ,default="draft",string='Status',required=True,copy=False,
                           help="When an asset is created the status is Draft\n"
                                "If a Book , an Assignment and a Source Line are added the statues goes in 'Capitalized' and the depreciation can be computed\n"
                                "You can manually close an asset by pressing 'Set To Retire' button ")
    # gross_value=fields.Float(required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, readonly=True,states={'draft': [('readonly', False)]},default=lambda self: self.env.user.company_id.currency_id.id)


    @api.multi
    def validation(self):
        if not self.book_assets_id and self.source_line_id:
            raise ValidationError("The fallowing fields should be entered in order to move to 'capitalize' state "
                                  "and be able to compute deprecation:"
                                  "- Book"
                                  "- Source Line")
        elif not self.book_assets_id :
            raise ValidationError ('Asset should be added to a Book')
        elif not self.source_line_id :
            raise ValidationError('source line should be added')
        else:
            self.state='capitalize'


    @api.onchange('book_assets_id')
    def guideline1(self):
        if self.book_assets_id:
            if not self.source_line_id:
                message="You should add a Source Line to be able to compute deprecation"
                warning = {
                            'title': _('Guideline!'),
                            'message': message ,
                        }
                return {'warning': warning}

    # @api.onchange('assignment_id')
    # def guideline2(self):
    #     if self.assignment_id :
    #         if len(self.source_line_id) == 0:
    #             warning = {
    #             'title': _('Guideline!'),
    #             'message': _('Add source line so the state change to Capitalize to be able to compute deprecation'),
    #             }
    #             return {'warning': warning}


    @api.model
    def create(self, values):
        values['name'] = self.env['ir.sequence'].next_by_code('asset_management.asset.Asset')
        record=super(Asset, self).create(values)
        # book_category=self.env['asset_management.category_books'].search([('book_id','=',record.default_book.id),('category_id','=',record.category_id.id)])
        # vals={
        #     'asset_id': record.id,
        #     'book_id': record.default_book.id,
        #     'method_time': book_category.method_time,
        #     'life_months': book_category.life_months,
        #     'method': book_category.depreciation_method,
        #     'original_cost': record.gross_value,
        #     'date_in_service':datetime.today()
        # }
        # record.env['asset_management.book_assets'].create(vals)
        # if record.source_line_id  and record.assignment_id and record.book_assets_id:
        #     record.state='capitalize'
        return record


    @api.multi
    def write(self, values):
        old_value=self.category_id
        super(Asset, self).write(values)
        if 'category_id' in values:
            if self.category_id != old_value:
                for record in self:
                    record.env['asset_management.transaction'].create({
                         'asset_id': record.id,
                         'trx_type': 're_class',
                         'trx_date': datetime.today(),
                         'category_id':record.category_id.id,
                         'trx_details':'old category : '+old_value.name+'\nnew category : '+record.category_id.name
                         })
                return record


    # @api.onchange('category_id')
    # def onchange_category_id(self):
    #     if self.category_id:
    #         self.asset_with_category = True
    #         res=[]
    #         default_book_domain=self.env['asset_management.category_books'].search([('category_id','=',self.category_id.id)])
    #         for x in default_book_domain:
    #             if x.book_id.active is True:
    #                 res.append(x.book_id.id)
    #         return {'domain': {'default_book': [('id', 'in', res)]
    #                 }}


    @api.multi
    def open_retired_window(self):
        return {
            'name': _('Retirement'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'asset_management.retirement',
            'target': 'current',
            'res_id':self.id
        }


    # @api.depends('assignment_id')
    # def _modify_percentage(self):
    #     for record in self:
    #         for assignment in record.assignment_id:
    #             record.percentage += assignment.percentage
    #
    #
    # @api.constrains('assignment_id')
    # def _checkpercentage(self):
    #     for record in self:
    #         # if record.percentage not in (0, 100):
    #         #     raise ValidationError("Assignment does not add up to 100")
    #         if float_compare(record.percentage,100.00, precision_digits=2) != 0 :
    #             raise ValidationError("Assignment does not add up to 100")


    @api.multi
    def generate_mas_entries(self,date,post_entries):
        new_moved_lines=[]
        old_moved_lines=[]
        capitalized_asset=self.env['asset_management.asset'].search([('state','=','capitalize')])
        for entries in capitalized_asset:
            dep_line = self.env['asset_management.depreciation'].search(
                [('asset_id', '=', entries.id), ('depreciation_date', '<=', date),('move_posted_check','=',False)])
            for deprecation in dep_line:
                if deprecation.move_check is False:
                    deprecation.create_move()
                    new_moved_lines +=deprecation
                else:
                    old_moved_lines +=deprecation
        if post_entries is False:
          return new_moved_lines
        else:
            new_moved_lines += old_moved_lines
            return new_moved_lines




class Category(models.Model):
    _name = 'asset_management.category'
    name = fields.Char(string='Category Name',index=True,required=True)
    description = fields.Text()
    ownership_type = fields.Selection(selection=[('owned', 'Owned')],default='owned')
    is_in_physical_inventory = fields.Boolean()
    category_books_id=fields.One2many('asset_management.category_books',inverse_name='category_id',on_delete='cascade',)
    depreciation_method = fields.Selection([('linear','Linear'),('degressive','Degressive')],
    default='linear')
    asset_with_category=fields.Boolean()
    active = fields.Boolean(default=True)

    _sql_constraints=[('name','UNIQE(name)','Category name already exist..!')]



class Book(models.Model):
    _name = 'asset_management.book'
    name = fields.Char(index=True,required=True)
    description = fields.Text()
    company_id=fields.Many2one('res.company', string='Company',required=True,default=lambda self: self.env['res.company']._company_default_get('asset_management.book'))
    # proceeds_of_sale_gain_account = fields.Many2one('account.account', on_delete='set_null')
    # proceeds_of_sale_loss_account = fields.Many2one('account.account', on_delete='set_null')
    # proceeds_of_loss_clearing_account = fields.Many2one('account.account', on_delete='set_null')
    cost_of_removal_gain_account = fields.Many2one('account.account', on_delete='set_null',domain=[('user_type_id','=','Income')])
    cost_of_removal_loss_account = fields.Many2one('account.account', on_delete='set_null',domain=[('user_type_id','=','Expenses')])
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
    _sql_constraints=[('name','UNIQUE(name)','Book name already exist..!')]


    @api.depends('company_id')
    def _compute_currency(self):
        self.currency_id=self.company_id.currency_id.id

    # @api.model
    # def create(self, values):
    #     values['name']=self.env['ir.sequence'].next_by_code('asset_management.book.Book')
    #     return super(Book, self).create(values)


class BookAssets (models.Model):
    _name='asset_management.book_assets'
    name=fields.Char( string="Book Asset Number",index=True)
    book_id = fields.Many2one('asset_management.book',on_delete= 'cascade',required=True,)
    asset_id = fields.Many2one('asset_management.asset',on_delete = 'cascade',readonly=True,string='Asset')
    depreciation_line_ids=fields.One2many(comodel_name='asset_management.depreciation',inverse_name='book_assets_id',on_delete='cascade')
    depreciation_line_length=fields.Integer(compute="_depreciation_line_length")
    current_cost = fields.Float(string = "Residual Value",compute='_amount_residual',required=True)
    salvage_value = fields.Float(compute='_compute_salvage_value')
    method = fields.Selection(
        [('linear','Linear'),
         ('degressive','Degressive')
         ],required=True,string='Depreciation Method',default='linear')
    life_months = fields.Integer(required=True)
    end_date=fields.Date()
    original_cost = fields.Float(string='Gross Value', required=True)
    salvage_value_type = fields.Selection(
        [('amount','Amount'),('percentage','Percentage')],default='amount'
    )
    salvage_value_amount=fields.Float(string='Salvage Value Amount')
    date_in_service = fields.Date(string = 'Date In Service',required=True)
    prorate_date= fields.Date(string = 'Prorate Date',compute="_compute_prorate_date")
    # prorate_convenction = fields.Selection(
    #     [('first','First Convention')]
    # )
    depreciated_flag = fields.Boolean(string='Depreciated',default =True)
    method_progress_factor = fields.Float(string='Degressive Factor',default=0.3,)
    method_number=fields.Integer(string='Number of Depreciation',help="The number of depreciations needed to depreciate your asset")
    # company_id = fields.Many2one('res.company', string='Company',default=lambda self: self.env['res.company']._company_default_get('asset_management.book_assets'))
    entry_count = fields.Integer(compute='_entry_count', string='# Asset Entries')
    method_time = fields.Selection([('number', 'Number of Entries'), ('end', 'Ending Date')], string='Time Method',required=True,default= 'number',
                                   help="Choose the method to use to compute the dates and number of entries.\n"
                                        "  * Number of Entries: Fix the number of entries and the time between 2 depreciations.\n"
                                        "  * Ending Date: Choose the time between 2 depreciations and the date the depreciations won't go beyond.")
    state = fields.Selection([('draft', 'Draft'), ('open', 'Running'), ('close', 'Close')], 'Status', required=True,
                             copy=False, default='draft',
                             help="When an asset is created, the status is 'Draft'.\n"
                                  "If the asset is confirmed, the status goes in 'Running' and the depreciation lines can be posted in the accounting.\n"
                                  "You can manually close an asset when the depreciation is over. If the last line of depreciation is posted, the asset automatically goes in that status.")
    asset_state=fields.Selection(related='asset_id.state')
    assignment_id=fields.One2many(comodel_name='asset_management.assignment',inverse_name='book_assets_id',on_delete='cascade')
    percentage = fields.Float(compute='_modify_percentage')


    @api.model
    def create(self, values):
        values['name'] = self.env['ir.sequence'].next_by_code('asset_management.book_assets.BookAssets')
        record = super(BookAssets, self).create(values)

        self.env['asset_management.transaction'].create({
            'asset_id': record.asset_id.id,
            'book_id': record.book_id.id,
            'category_id': record.asset_id.category_id.id,
            'trx_type': 'addition',
            'trx_date': datetime.today(),
            'trx_details': 'New Asset ' +record.asset_id.name + ' Is Added to the Book: ' + record.book_id.name
        })

        self.env['asset_management.transaction'].create({
            'asset_id': record.asset_id.id,
            'book_id': record.book_id.id,
            'category_id': record.asset_id.category_id.id,
            'trx_type': 'cost_adjustment',
            'trx_date': datetime.today(),
            'trx_details': 'Old Gross Value  Is: '+str(0.00) + '\nNew Gross Vale Is: ' + str(record.original_cost)
        })

        return record


    @api.multi
    def write(self, values):
        old_gross_value = self.original_cost
        super(BookAssets, self).write(values)
        if 'original_cost' in values:
            for record in self:
                self.env['asset_management.transaction'].create({
                    'asset_id': record.asset_id.id,
                    'book_id': record.book_id.id,
                    'category_id': record.asset_id.category_id.id,
                    'trx_type': 'cost_adjustment',
                    'trx_date': datetime.today(),
                    'trx_details': 'Old Gross Value  Is: ' + str(old_gross_value) + '\nNew Gross Vale Is: ' + str(
                        self.original_cost)
                })

    @api.one
    @api.depends('date_in_service')
    def _compute_prorate_date(self):
        asset_date = datetime.strptime(self.date_in_service[:7] + '-01', DF).date()
        self.prorate_date=asset_date



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
        # if self._context.get('category_id'):
            res=[]
            # default_book=self._context.get('default_book')
            book_domain=self.env['asset_management.category_books'].search([('category_id','=',self._context.get('category_id'))])
                                                                               # ,('book_id','!=',default_book)])
            for book in book_domain:
                if book.book_id.active is True:
                    for existbook in self:
                        if existbook.book_id.id != book.book_id.id:
                            res.append(book.book_id.id)
            return {'domain': {'book_id': [('id', 'in', res)]
                    }}


    @api.multi
    def validate(self):
        assign_in_book_asset = self.env['asset_management.assignment'].search([('asset_id', '=', self.asset_id.id), ('book_id', '=', self.book_id.id)])
        if not assign_in_book_asset:
            raise UserError("you should assign the asset to a location")
        self.write({'state': 'open'})


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
                raise ValidationError("Assignment does not add up to 100")


    @api.one
    @api.depends('original_cost', 'salvage_value', 'depreciation_line_ids.move_check', 'depreciation_line_ids.amount')
    def _amount_residual(self):
        total_amount = 0.0
        for line in self.depreciation_line_ids:
            if line.move_check:
                total_amount += line.amount
        self.current_cost = self.original_cost - total_amount - self.salvage_value


    def _compute_board_undone_dotation_nb(self, depreciation_date):
        if self.method_time == 'end':
            if self.end_date is False:
                raise ValidationError ('End Date Is Required !')
            end_date = datetime.strptime(self.end_date, DF).date()
            undone_dotation_number = 0
            while depreciation_date <= end_date:
                depreciation_date = date(depreciation_date.year, depreciation_date.month,
                                         depreciation_date.day) + relativedelta(months=+self.life_months)
                undone_dotation_number += 1
        else:
            if self.method_number == 0 :
                raise ValidationError ('Number of Depreciation Is Should Not be 0 ')
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

        posted_depreciation_line_ids = self.depreciation_line_ids.filtered(lambda x: x.move_check).sorted(
            key=lambda l: l.depreciation_date)
        unposted_depreciation_line_ids = self.depreciation_line_ids.filtered(lambda x: not x.move_check)

        # Remove old unposted depreciation lines. We cannot use unlink() with One2many field
        commands = [(2, line_id.id, False) for line_id in unposted_depreciation_line_ids]

        if self.current_cost != 0.0:
            amount_to_depr = residual_amount = self.current_cost
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
                    'depreciated_value': self.original_cost - (self.salvage_value + residual_amount),
                    'depreciation_date': depreciation_date.strftime(DF),
                }
                commands.append((0, False, vals))
                # Considering Depr. Period as months
                depreciation_date = date(year, month, day) + relativedelta(months=+self.life_months)
                day = depreciation_date.day
                month = depreciation_date.month
                year = depreciation_date.year

        self.write({'depreciation_line_ids':commands})
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
    def _entry_count(self):
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
            category_book = self.env['asset_management.category_books'].search([('book_id', '=', book_id),('category_id', '=', self.asset_id.category_id.id)])
            return{
                'value' : {
                'method': category_book.depreciation_method,
                'method_time':category_book.method_time,
                'life_months':category_book.life_months,
                'method_number':category_book.method_number,

                    }
                }


#to hide the depreciation compute button
    @api.depends('depreciation_line_ids')
    def _depreciation_line_length(self):
        self.depreciation_line_length=len(self.depreciation_line_ids)


#compute percentage for salvage value
    @api.one
    @api.depends('salvage_value_type','salvage_value_amount')
    def _compute_salvage_value(self):
        if self.salvage_value_type == 'amount':
            self.salvage_value=self.salvage_value_amount
        elif self.salvage_value_type=='percentage':
            self.salvage_value=(self.salvage_value_amount * self.original_cost)/100


    @api.multi
    def move_to_book_asset(self):
        #view_id = self.env.ref('asset_management.book_assets_form_view').id
        return{
                         'type': 'ir.actions.act_window',
                         'name': _(' Asset In Book'),
                         'view_type': 'form',
                         'view_mode': 'form',
                         #'view_id':view_id,
                         'res_model': 'asset_management.book_assets',
                         'res_id':self.id,
                         'target': 'current',

           }


#    @api.model
 #    def _cron_generate_entries(self):
 #        self.compute_generated_entries(datetime.today())
 #
 #
 # #used in asset_depreciation confirmation wizard
 #    @api.model
 #    def compute_generated_entries(self, date, asset_type=None):
 #        # Entries generated : one by grouped category and one by asset from ungrouped category
 #        created_move_ids = []
 #        type_domain = []
 #        if asset_type:
 #            type_domain = [('type', '=', asset_type)]
 #
 #        # ungrouped_assets = self.env['asset_management.asset'].search(type_domain + [('state', '=', 'open'), ('category_id.group_entries', '=', False)])
 #        # created_move_ids += ungrouped_assets._compute_entries(date, group_entries=False)
 #
 #        for grouped_category in self.env['asset_management.category'].search(type_domain + [('group_entries', '=', True)]):
 #            assets = self.env['asset_management.asset'].search([('state', '=', 'open'), ('category_id', '=', grouped_category.id)])
 #            created_move_ids += assets._compute_entries(date, group_entries=True)
 #        return created_move_ids



class Assignment(models.Model):
    _name = 'asset_management.assignment'
    name = fields.Char(string="Assignment",readonly='True',index=True)
    book_assets_id = fields.Many2one('asset_management.book_assets',on_delete = 'cascade',required=True)
    book_id = fields.Many2one("asset_management.book", string="Book",on_delete = 'cascade',required=True,compute="_get_book_name")
    asset_id = fields.Many2one("asset_management.asset", string="Asset", on_delete='cascade',required=True,compute="_get_asset_name")
    depreciation_expense_account=fields.Many2one('account.account',on_delete='set_null',required=True)
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
    def onchange_id(self):
        # if not self.book_assets_id:
        #     return

        category_book = self.env['asset_management.category_books'].search(
            [('book_id','=', self.book_id.id), ('category_id','=', self.asset_id.category_id.id)])
        value = {
            'depreciation_expense_account':category_book.depreciation_expense_account
        }
        for k, v in value.items():
            setattr(self, k, v)

        # category=self.asset_id.category_id.id
        # res = []
        # book_domain = self.env['asset_management.category_books'].search(
        #             [('category_id', '=', category)])
        # for x in book_domain:
        #     if x.book_id.active is True:
        #             res.append(x.book_id.id)
        # return {'domain': {'book_id': [('id', 'in', res)]
        #                            }}


#creat transaction record when adding a new assignment and location
    @api.model
    def create(self, values):
        values['name']=self.env['ir.sequence'].next_by_code('asset_management.assignment.Assignment')
        record=super(Assignment, self).create(values)
        record.env['asset_management.transaction'].create({
            'book_id':self.book_id.id,
            'asset_id': record.asset_id.id,
            'category_id': record.asset_id.category_id.id,
            'trx_type': 'transfer',
            'trx_date': datetime.today(),
            'trx_details': 'Responsible : '+str(record.responsible_id.name)+'\nLocation : '+record.location_id.name
        })
        return record

    @api.depends('book_assets_id')
    def _get_asset_name(self):
        asset= self.asset_id=self.book_assets_id.asset_id.id
        return asset


    @api.depends('book_assets_id')
    def _get_book_name(self):
        self.book_id=self.book_assets_id.book_id.id
        return self.book_id



#create transaction when changing responsible or location
    @api.multi
    def write(self,values):
        old_responsible=self.responsible_id
        old_location=self.location_id
        super(Assignment, self).write(values)
        if 'responsible_id' in values:
            if  self.responsible_id != old_responsible :
                self.env['asset_management.transaction'].create({
                    'asset_id':self.asset_id.id,
                    'book_id':self.book_id.id,
                    'category_id':self.asset_id.category_id.id,
                    'trx_type':'transfer',
                    'trx_date':datetime.today(),
                    'trx_details':'Old Responsible : '+str(old_responsible.name)+'\nNew Responsible : '+self.responsible_id.name ,
                                                                })
        if 'location_id' in values:
            if self.location_id != old_location :
                self.env['asset_management.transaction'].create({
                    'asset_id': self.asset_id.id,
                    'book_id':self.book_id.id,
                    'category_id': self.asset_id.category_id.id,
                    'trx_type': 'transfer',
                    'trx_date': datetime.today(),
                    'trx_details': 'Old Location : '+old_location.name+'\nNew Location : '+self.location_id.name,
                })


class SourceLine(models.Model):
    _name = 'asset_management.source_line'
    name = fields.Char(string="Source Line Number",readonly=True,index=True)
    asset_id = fields.Many2one('asset_management.asset',on_delete = 'cascade',readonly=True)
    source_type = fields.Selection(
        [
            ('invoice','Invoice'),
        ]
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

    # @api.one
    # @api.depends('asset_id.item_id','invoice_id')
    # def _get_invoice_line(self):
    #     product=self.asset_id.item_id.id
    #     for invoice_line in self.invoice_id.invoice_line_ids:
    #         if invoice_line.product_id.id == product:
    #             self.invoice_line_ids=invoice_line


    @api.one
    @api.depends('invoice_id','invoice_line_ids')
    def _get_price_from_invoice(self):
        self.amount=self.invoice_line_ids.price_unit


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
    move_check = fields.Boolean(compute='_get_move_check', string='Linked', track_visibility='always', store=True)
    move_posted_check = fields.Boolean(compute='_get_move_posted_check', string='Posted', track_visibility='always',store=True)
    parent_state = fields.Selection(related="book_assets_id.state", string='State of Asset')




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


# generate entries in account.move
    @api.multi
    def create_move(self, post_move=True):
        created_moves = self.env['account.move']
        prec = self.env['decimal.precision'].precision_get('Account')
        # current_currency = self.env['res.company'].search([('id','=',1)])[0].currency_id
        journal_id=self.env['asset_management.category_books'].search([('book_id', '=', self.book_id.id),('category_id', '=', self.asset_id.category_id.id)]).journal_id
        for line in self:
            if line.move_id:
                raise UserError(
                    _('This depreciation is already linked to a journal entry! Please post or delete it.'))
            # category_id = line.asset_id.category_id
            company_currency=line.book_id.company_id.currency_id
            current_currency=line.asset_id.currency_id
            depreciation_date = self.env.context.get('depreciation_date') or line.depreciation_date or fields.Date.context_today(self)
            accumulated_depreciation_account = line.env['asset_management.category_books'].search( [('book_id', '=', self.book_id.id), ('category_id', '=', self.asset_id.category_id.id)])[0].accumulated_depreciation_account
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
                amount = current_currency.with_context(date=depreciation_date).compute(amount,company_currency)
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
            created_moves |= move
            #source_line=self.env['asset_management.source_line'].search([('asset_id','=',self.asset_id.id),('source_type','=','invoice')])
            # if post_move and created_moves:
            #     created_moves.filtered(
            #         lambda m: any(m.asset_depreciation_id.mapped('asset_id.source_line_id'))).post()
            return [x.id for x in created_moves]



#generat entries in account.move based on category_grouped

    # @api.multi
    # def create_grouped_move(self, post_move=True):
    #     created_moves = self.env['account.move']
    #     current_currency = self.env['res.company'].search([('id', '=', 1)])[0].currency_id
    #     journal_id = self.book_id.jounal_id.id
    #     for line in self:
    #         category_id = line.asset_id.category_id
    #         depreciation_date = self.env.context.get('depreciation_date') or line.depreciation_date or fields.Date.context_today(self)
    #         asset_cost_account = line.env['assset_management.category_books'].search([('book_id', '=', self.book_id.id), ('category_id', '=', self.asset_id.category_id.id)])[0].accumulated_depreciation_account
    #         depreciation_expense_account = line.env['assset_management.category_books'].search([('book_id', '=', self.book_id.id), ('category_id', '=', self.asset_id.category_id.id)])[0].depreciation_expense_account
    #         partner_id = line.env['asset_management.source_line'].search([('asset_id', '=', self.asset_id.id)])[0].invoice_id.partner_id
    #         amount = current_currency.compute(line.amount, current_currency)
    #         move_line_1 = {
    #             'name': line.asset_id.name,
    #             'account_id': asset_cost_account.id,
    #             'debit': 0.0,
    #             'credit': amount,
    #             'journal_id': journal_id,
    #             'analytic_account_id': False,
    #         }
    #         move_line_2 = {
    #             'name': line.asset_id.name,
    #             'account_id': depreciation_expense_account.id,
    #             'credit': 0.0,
    #             'debit': amount,
    #             'journal_id': journal_id,
    #             'analytic_account_id': False,
    #         }
    #         move_vals = {
    #             'ref': line.asset_id.name,
    #             'date': depreciation_date or False,
    #             'journal_id': journal_id,
    #             'line_ids': [(0, 0, move_line_1), (0, 0, move_line_2)],
    #         }
    #         move = self.env['account.move'].create(move_vals)
    #         line.write({'move_id': move.id, 'move_check': True})
    #         created_moves |= move
    #
    #         if post_move and created_moves:
    #             self.post_lines_and_close_asset()
    #             created_moves.post()
    #         return [x.id for x in created_moves]


    @api.multi
    def post_lines_and_close_asset(self):
        # we re-evaluate the assets to determine whether we can close them
        for line in self:
            # line.log_message_when_posted()
            asset = line.asset_id
            book=line.book_id
            book_asset=line.env['asset_management.book_assets'].search([('asset_id','=',asset.id),('book_id','=',book.id)])
            current_cost=book_asset[0].current_cost
            current_currency = self.env['res.company'].search([('id', '=', 1)])[0].currency_id
            if current_currency.is_zero(current_cost):
                #asset.message_post(body=_("Document closed."))
                book_asset.write({'state': 'close'})


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
    #             partner_name = line.env['asset_management.source_line'].search([('asset_id','=',self.asset_id.id)])[0].invoice_id.partner_id
    #             currency_name = self.env['res.company'].search([('id','=',1)])[0].currency_id
    #             msg_values = {_('Currency'): currency_name, _('Amount'): line.amount}
    #             if partner_name:
    #                 msg_values[_('Partner')] = partner_name
                #msg = _format_message(_('Depreciation line posted.'), msg_values)
                #line.asset_id.message_post(body=msg)


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
    book_assets_id = fields.Many2one('asset_management.book_assets',on_delete = 'cascade')
    book_id=fields.Many2one('asset_management.book',on_delete = 'cascade',required=True,domain=[('active','=',True)])
    asset_id = fields.Many2one('asset_management.asset', on_delete='cascade',readonly=True)
    retire_date = fields.Date(string = 'Retire Date')
    comments = fields.Text(string = "Comments")
    residual_value = fields.Float(string= "Residual Value")
    units_retired = fields.Integer(string ='Units Retired')
    current_units = fields.Integer(string="Units to Assign")
    gain_loss_amount=fields.Float()
    proceeds_of_sale = fields.Float()
    cost_of_removal= fields.Float()
   # sold_to=fields.Char()
    partner_id = fields.Many2one(comodel_name="res.partner", string="Sold To")
    check_invoice= fields.Char()


    @api.model
    def create(self, values):
        values['name'] = self.env['ir.sequence'].next_by_code('asset_management.retirement.Retirement')
        return super(Retirement,self).create(values)


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



    @api.model
    def create(self, values):
        values['name'] = self.env['ir.sequence'].next_by_code('asset_management.category_books.CategoryBooks')
        return super(CategoryBooks, self).create(values)


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
    trx_details = fields.Text('Transaction Details')
    # period = fields.Selection(
    #     [('1','JAN'),
    #      ('2','FEB'),
    #      ('3','MAR')]
    # )


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
    name = fields.Char(string='Street')
    city=fields.Char(required=True)
    state_id=fields.Many2one('res.country.state')
    country_id=fields.Many2one('res.country',required=True)
    active=fields.Boolean(default=True)


