from __future__ import unicode_literals
import json
import requests
import frappe
import time
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
from frappe.utils.password import get_decrypted_password
from erpnext.stock.doctype import shipment, shipment_parcel
from erpnext_shipping.erpnext_shipping.doctype.novaposhta.np_client import NovaPoshtaApi
from erpnext_shipping.erpnext_shipping.doctype.novaposhta_settings.novaposhta_settings import NovaPoshtaSettings
from erpnext_shipping.erpnext_shipping.utils import show_error_alert
from requests import post, get
from time import sleep

NOVAPOSHTA_PROVIDER = 'NovaPoshta'


class NovaPoshtaUtils:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or get_decrypted_password('NovaPoshta', 'NovaPoshta', 'api_key', raise_exception=False)
        self.api_id, self.enabled = frappe.db.get_value('NovaPoshta', 'NovaPoshta', ['api_id', 'enabled'])
        self.print_uri = frappe.db.get_value('NovaPoshta', 'NovaPoshta', 'print_uri')
        self.api_endpoint = 'https://api.novaposhta.ua/v2.0/json/'

        if not self.enabled:
            link = frappe.utils.get_link_to_form('NovaPoshta', 'NovaPoshta', frappe.bold('NovaPoshta Settings'))
            frappe.throw(_('Please enable NovaPoshta Integration in {0}'.format(link)), title=_('Mandatory'))

        self.novaposhta_api = NovaPoshtaApi(api_key=self.api_key)

    def get_available_services(self, **kwargs) -> requests.Response:
        headers = {'content-type': 'application/json'}
        kwargs['modelName'] = 'InternetDocument'
        kwargs['calledMethod'] = 'getDocumentPrice'
        kwargs['apiKey'] = self.api_key

        form=kwargs
        pickup_warehouse = self.get_warehoouse_ref(
            city=form['pickup_address']['city'],
            title=form['pickup_address']['address_title']
        )['data'][0] 
        sleep(1)

        delivery_warehouse = self.get_warehoouse_ref(
            city=form['delivery_address']['city'],
            title=form['delivery_address']['address_title']
        )['data'][0]
        
        delivery_price_data = self.calculate_delivery_price(
            city_sender=pickup_warehouse['SettlementRef'],
            city_recipient=delivery_warehouse['SettlementRef'],
            weight='10',
            cost=form['value_of_goods'],
            seats_amount = '1',
            pack_count = '1'
        )
        
        data = delivery_price_data.get('data', [])
        
        if len(data) == 0:
            return []
        
        result = {
            'Nova Poshta service':[
                    {
                        'service_type_name': 'Nova Poshta',
                        'carrier_name': 'Nova Poshta',
                        'service_provider': 'NP',
                        'service_name': 'WarehouseWarehouse delivery',
                        'Price': data[0]['Cost']
                    }
                ]
        }
        
        # url = self.api_endpoint #+ 'InternetDocument/GetDocumentPrice'
        # response = requests.post(url, data=json.dumps(kwargs), headers=headers)
        return result
        

    def get_novaposhta_shipping_rates(self, args):
        novaposhta = NovaPoshtaUtils()
        shipment_parcel_data = args.get('shipment_parcel')
        if shipment_parcel_data:
            shipment_parcel_data = json.loads(shipment_parcel_data)
        if shipment_parcel_data:
            shipment_parcel_data = shipment_parcel_data[0]
        else:
            frappe.throw(_('Shipment Parcel data not found'))

        shipping_rates = novaposhta.novaposhta_api.get_novaposhta_shipping_rates(
            recipient_city_ref=args.get('recipient_city_ref'),
            sender_city_ref=args.get('sender_city_ref'),
            service_type=args.get('service_type'),
            cargo_type=args.get('cargo_type'),
            weight=flt(shipment_parcel_data.get('weight')),
            cost_of_goods=flt(args.get('value_of_goods'))
        )
        return shipping_rates
    
    def calculate_delivery_price(self, city_sender, city_recipient, weight, cost, seats_amount = '1', pack_count = '1'):
        body = {
            "apiKey": self.api_key,
            "modelName": "InternetDocument",
            "calledMethod": "getDocumentPrice",
            "methodProperties": {
                "CitySender" : city_sender,
                "CityRecipient" : city_recipient,
                "Weight" : weight,
                "ServiceType" : "WarehouseWarehouse",
                "Cost" : cost,
                "CargoType" : "Cargo",
                "SeatsAmount" : seats_amount,
                "RedeliveryCalculate" : {
                    "CargoType":"Money",
                    "Amount":"100"
                },
                "PackCount" : pack_count
            }
        }
        response = post(self.api_endpoint, json=body)
        return response.json()
    
    def get_warehoouse_ref(self, city, title):
        body = {
            "apiKey": self.api_key,
            "modelName": "Address",
            "calledMethod": "getWarehouses",
            "methodProperties": {
                "CityName" : city,
                "Page" : "1",
                "Limit" : "50",
                "Language" : "UA",
                "FindByString": title
            }
        }
        response = post(self.api_endpoint, json=body)
        return response.json()


@frappe.whitelist()
def fetch_shipping_rates(args):
    args = json.loads(args)
    # Convert parcel data from JSON to a list
    parcel_data = json.loads(args['shipment_parcel'])

    # Fetch shipping rates from various carriers
    novaposhta_utils = NovaPoshtaUtils()
    try:
        novaposhta_prices = novaposhta_utils.get_novaposhta_shipping_rates(args)
    except Exception as e:
        show_error_alert(str(e))
        return []

    # Ensure novaposhta_prices is a list
    if not isinstance(novaposhta_prices, list):
        novaposhta_prices = [novaposhta_prices]

    # Combine all shipping rates into a single list
    shipment_prices = novaposhta_prices

    # Return the list of shipping rates
    return shipment_prices

    
def create_shipment(self, shipment_data):
    try:
        # Create a shipment
        novaposhta = NovaPoshtaUtils()
        shipment_parcel_data = shipment_data.get('shipment_parcel')
        if shipment_parcel_data:
            shipment_parcel_data = json.loads(shipment_parcel_data)
        if shipment_parcel_data:
            shipment_parcel_data = shipment_parcel_data[0]
        else:
            frappe.throw(_('Shipment Parcel data not found'))

        shipment_doc = shipment_data()
        shipment_doc.update({
            'shipment_type': 'Outgoing',
            'customer': shipment_data.get('customer'),
            'customer_address': shipment_data.get('customer_address'),
            'from_warehouse': shipment_data.get('from_warehouse'),
            'to_warehouse': shipment_data.get('to_warehouse'),
            'to_address': shipment_data.get('to_address'),
            'to_city': shipment_data.get('to_city'),
            'to_state': shipment_data.get('to_state'),
            'to_country': shipment_data.get('to_country'),
            'to_pincode': shipment_data.get('to_pincode'),
            'total_weight': flt(shipment_parcel_data.get('weight')),
            'grand_total': flt(shipment_data.get('value_of_goods')),
            'nova_poshta_tracking_number': 'IntDocNumber',
            'nova_poshta_provider': NOVAPOSHTA_PROVIDER
        })
        shipment_doc.save()

        shipment_parcel_doc = shipment_parcel_data()
        shipment_parcel_doc.update({
            'parenttype': 'Shipment',
            'parentfield': 'shipment_parcel',
            'parent': shipment_doc.name,
            'item_code': shipment_data.get('item_code'),
            'qty': shipment_data.get('qty'),
            'weight': flt(shipment_parcel_data.get('weight')),
            'value': flt(shipment_data.get('value_of_goods'))
        })
        shipment_parcel_doc.save()

        shipment_doc.reload()

        shipment_doc.shipment_parcel = [shipment_parcel_doc]

        shipment_doc.save()

        shipment_doc.submit()

        return shipment_doc
    except Exception as e:
        frappe.log_error('Error creating shipment: {}'.format(str(e)))
        frappe.throw(_('Error creating shipment: {}'.format(str(e))))


@frappe.whitelist()
def create_novaposhta_shipment(shipment_data):
    try:
        # Create a shipment
        shipment_data = json.loads(shipment_data)
        shipment_doc = create_shipment(None, shipment_data)

        # Create a shipment in Nova Poshta
        novaposhta = NovaPoshtaUtils()
        shipment_parcel_data = shipment_data.get('shipment_parcel')
        if shipment_parcel_data:
            shipment_parcel_data = json.loads(shipment_parcel_data)
        if shipment_parcel_data:
            shipment_parcel_data = shipment_parcel_data[0]
        else:
            frappe.throw(_('Shipment Parcel data not found'))

        shipment = novaposhta.create_novaposhta_shipment({
            'recipient_city_ref': shipment_data.get('to_city_ref'),
            'sender_city_ref': shipment_data.get('from_city_ref'),
            'service_type': shipment_data.get('service_type'),
            'cargo_type': shipment_data.get('cargo_type'),
            'shipment_parcel': [shipment_parcel_data],
            'value_of_goods': shipment_data.get('value_of_goods'),
            'recipient_name': shipment_data.get('customer'),
            'recipient_phone': shipment_data.get('customer_phone'),
            'recipient_email': shipment_data.get('customer_email'),
            'recipient_address': shipment_data.get('to_address'),
            'recipient_warehouse_ref': shipment_data.get('to_warehouse_ref'),
            'sender_name': shipment_data.get('from_address_name'),
            'sender_phone': shipment_data.get('from_address_phone'),
            'sender_email': shipment_data.get('from_address_email'),
            'sender_address': shipment_data.get('from_address'),
            'sender_warehouse_ref': shipment_data.get('from_warehouse_ref'),
            'description': shipment_data.get('description')
        })

        # Update the shipment with the Nova Poshta tracking number
        shipment_doc.nova_poshta_tracking_number = shipment.get('IntDocNumber')
        shipment_doc.save()

        # Print the shipping label
        if novaposhta.print_uri:
            novaposhta.novaposhta_api.print_label(shipment.get('IntDocNumber'), novaposhta.print_uri)

        return shipment_doc
    except Exception as e:
        frappe.log_error('Error creating Nova Poshta shipment: {}'.format(str(e)))
        frappe.throw(_('Error creating Nova Poshta shipment: {}'.format(str(e))))
    
