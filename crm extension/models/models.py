# -*- coding: utf-8 -*-

from odoo import models, fields, api,tools,_
import threading
import base64
from odoo.modules import get_module_resource

class CrmExtension(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _get_default_image(self, partner_type, is_company, parent_id):
        if getattr(threading.currentThread(), 'testing', False) or self._context.get('install_mode'):
           return False

        colorize, img_path, image = False, False, False

        if partner_type in ['other'] and parent_id:
           img_path = get_module_resource('base', 'static/src/img', 'avatar.png')
           colorize = True

        if not image and partner_type == 'invoice':
               img_path = get_module_resource('base', 'static/src/img', 'money.png')
        elif not image and partner_type == 'delivery':
               img_path = get_module_resource('base', 'static/src/img', 'truck.png')
        elif not image and is_company:
               img_path = get_module_resource('base', 'static/src/img', 'company_image.png')
        elif not image:
               img_path = get_module_resource('base', 'static/src/img', 'avatar.png')
               colorize = True

        if img_path:
               with open(img_path, 'rb') as f:
                   image = f.read()
        if image and colorize:
               image = tools.image_colorize(image)

        return tools.image_resize_image_big(base64.b64encode(image))