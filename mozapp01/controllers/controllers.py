# -*- coding: utf-8 -*-
from odoo import http

# class Mozapp01(http.Controller):
#     @http.route('/mozapp01/mozapp01/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/mozapp01/mozapp01/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('mozapp01.listing', {
#             'root': '/mozapp01/mozapp01',
#             'objects': http.request.env['mozapp01.mozapp01'].search([]),
#         })

#     @http.route('/mozapp01/mozapp01/objects/<model("mozapp01.mozapp01"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('mozapp01.object', {
#             'object': obj
#         })