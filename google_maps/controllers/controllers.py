# -*- coding: utf-8 -*-
from odoo import http

# class Google-maps(http.Controller):
#     @http.route('/google-maps/google-maps/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/google-maps/google-maps/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('google-maps.listing', {
#             'root': '/google-maps/google-maps',
#             'objects': http.request.env['google-maps.google-maps'].search([]),
#         })

#     @http.route('/google-maps/google-maps/objects/<model("google-maps.google-maps"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('google-maps.object', {
#             'object': obj
#         })