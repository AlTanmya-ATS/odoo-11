# -*- coding: utf-8 -*-
from odoo import http

# class CrmExtend(http.Controller):
#     @http.route('/crm_extend/crm_extend/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/crm_extend/crm_extend/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('crm_extend.listing', {
#             'root': '/crm_extend/crm_extend',
#             'objects': http.request.env['crm_extend.crm_extend'].search([]),
#         })

#     @http.route('/crm_extend/crm_extend/objects/<model("crm_extend.crm_extend"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('crm_extend.object', {
#             'object': obj
#         })