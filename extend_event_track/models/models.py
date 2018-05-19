# -*- coding: utf-8 -*-

from odoo import models, fields, api,_
from datetime import date, datetime
from odoo.exceptions import UserError, AccessError, ValidationError

class TrackAttendee(models.Model):
        _name='track.attendee'
        _inherit='event.registration'
        track_id = fields.Many2one(comodel_name = "event.track", required = True,on_delete="cascade")
        state = fields.Selection([('open', 'Confirmed'),
            ('present', 'Present'), ('absent', 'Absent'),
             ('late', 'Late'),('excused','Excused'),('compensated','Compensated'),('left_early','Left Early')],default='open',
            string='Status', readonly = False )


        @api.one
        def button_reg_close(self):
            today = fields.Datetime.now()
            if self.event_id.date_begin <= today and self.event_id.state == 'confirm':
                self.write({'state': 'present', 'date_closed': today})
            elif self.event_id.state == 'draft':
                raise UserError(_("You must wait the event confirmation before doing this action."))
            else:
                raise UserError(_("You must wait the event starting day before doing this action."))

        @api.one
        def button_reg_absent(self):
            today = fields.Datetime.now()
            self.write({'state': 'absent', 'date_closed': today})



class EventTrack(models.Model):
    _inherit='event.track'
    attendee_id = fields.One2many(comodel_name="track.attendee", inverse_name="track_id",)
    invisible_button=fields.Boolean(default=False)
    attendee_id_len=fields.Integer(compute='_attendee_length')
    notes = fields.Text(string="Notes")


    @api.multi
    def attendee_name(self):
        partner_ids = self.env['event.registration'].search([('event_id', '=', self.event_id.id),('state','=','open')])
        if not partner_ids:
            raise UserError(_('NO attendance in the event !'))
        else:
            for attendee in partner_ids:
                values = {
                    'partner_id': attendee.partner_id.id,
                    'name': attendee.name,
                    'email': attendee.email,
                    'phone': attendee.phone,
                    'event_id': self.event_id.id,
                    'state': attendee.state,
                }
                self.write({'attendee_id': [(0, False, values)]})
        self.invisible_button=True
        return True

    @api.depends('attendee_id')
    def _attendee_length(self):
        self.attendee_id_len = len(self.attendee_id)
        if self.attendee_id_len == 0:
            self.invisible_button = False
        # else:
        #     self.invisible_button = False













