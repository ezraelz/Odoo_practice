from odoo import models, fields, api
import requests

class EthiopianHoliday(models.Model):
    _name = "ethiopian.holiday"
    _description = "Ethiopian Holiday"

    name = fields.Char(required=True)
    date = fields.Date(required=True)
    type = fields.Char()
    event_id = fields.Many2one("calendar.event", ondelete="cascade")

    _sql_constraints = [
        ('unique_date_name', 'unique(date, name)', 'Holiday already exists!')
    ]

    def sync_holidays(self):
        url = "https://api.ethioall.com/events/api"
        response = requests.get(url, timeout=10)
        data = response.json()

        for item in data:
            exists = self.search([
                ('date', '=', item['date']),
                ('name', '=', item['name'])
            ], limit=1)

            if not exists:
                holiday = self.create({
                    'name': item['name'],
                    'date': item['date'],
                    'type': item.get('type', ''),
                })

                # Create calendar event
                event = self.env['calendar.event'].create({
                    'name': holiday.name,
                    'start': holiday.date,
                    'stop': holiday.date,
                    'allday': True,
                })

                holiday.event_id = event.id
                