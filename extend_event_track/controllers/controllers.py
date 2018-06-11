# -*- coding: utf-8 -*-
from odoo import http

# class ExtendEventTrack(http.Controller):
#     @http.route('/extend_event_track/extend_event_track/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/extend_event_track/extend_event_track/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('extend_event_track.listing', {
#             'root': '/extend_event_track/extend_event_track',
#             'objects': http.request.env['extend_event_track.extend_event_track'].search([]),
#         })

#     @http.route('/extend_event_track/extend_event_track/objects/<model("extend_event_track.extend_event_track"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('extend_event_track.object', {
#             'object': obj
#         })