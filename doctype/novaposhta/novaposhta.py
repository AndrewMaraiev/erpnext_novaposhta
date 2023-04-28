from __future__ import unicode_literals
import json
import requests
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
from frappe.utils.password import get_decrypted_password
from erpnext.stock.doctype import shipment, shipment_parcel
from erpnext_shipping.erpnext_shipping.doctype.novaposhta.np_client import NovaPoshtaApi
from erpnext_shipping.erpnext_shipping.doctype.novaposhta_settings.novaposhta_settings import NovaPoshtaSettings
from erpnext_shipping.erpnext_shipping.utils import show_error_alert

NOVAPOSHTA_PROVIDER = 'NovaPoshta'


class NovaPoshta(Document):
    pass


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
        frappe.msgprint(str(kwargs))
        url = self.api_endpoint #+ 'InternetDocument/GetDocumentPrice'
        response = requests.post(url, data=json.dumps(kwargs), headers=headers)
        return response.text

    def get_novaposhta_shipping_rates(self, args):
        novaposhta = NovaPoshtaUtils()
        shipment_parcel_data = args.get('shipment_parcel')
        if shipment_parcel_data:
            shipment_parcel_data = json.loads(shipment_parcel_data)
        if shipment_parcel_data:
            shipment_parcel_data = shipment_parcel_data[0]
        else:
            frappe.throw(_('Shipment Parcel data not found'))

        shipping_rates = novaposhta.novaposhta_api.get_shipping_rates(
            recipient_city_ref=args.get('recipient_city_ref'),
            sender_city_ref=args.get('sender_city_ref'),
            service_type=args.get('service_type'),
            cargo_type=args.get('cargo_type'),
            weight=flt(shipment_parcel_data.get('weight')),
            cost_of_goods=flt(args.get('value_of_goods'))
        )
        return shipping_rates


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

    
def get_create_shipment(self, shipment_data):
        # Create a shipment
        novaposhta = NovaPoshtaUtils()
        shipment_parcel_data = shipment_data.get('shipment_parcel')
        if shipment_parcel_data:
            shipment_parcel_data = json.loads(shipment_parcel_data)
        if shipment_parcel_data:
            shipment_parcel_data = shipment_parcel_data[0]
        else:
            frappe.throw(_('Shipment Parcel data not found'))

        shipment = novaposhta.novaposhta_api.create_shipment(
            recipient_city_ref=shipment_data.get('recipient_city_ref'),
            sender_city_ref=shipment_data.get('sender_city_ref'),
            service_type=shipment_data.get('service_type'),
            cargo_type=shipment_data.get('cargo_type'),
            weight=flt(shipment_parcel_data.get('weight')),
            cost_of_goods=flt(shipment_data.get('value_of_goods')),
            recipient_name=shipment_data.get('recipient_name'),
            recipient_phone=shipment_data.get('recipient_phone'),
            recipient_email=shipment_data.get('recipient_email'),
            recipient_address=shipment_data.get('recipient_address'),
            recipient_warehouse_ref=shipment_data.get('recipient_warehouse_ref'),
            sender_name=shipment_data.get('sender_name'),
            sender_phone=shipment_data.get('sender_phone'),
            sender_email=shipment_data.get('sender_email'),
            sender_address=shipment_data.get('sender_address'),
            sender_warehouse_ref=shipment_data.get('sender_warehouse_ref'),
            description=shipment_data.get('description')
        )
        return shipment
        
    
        
    

        
        
    
    
    # def get_available_services(self, **kwargs):
    #    print(kwargs)
    #   # kwargs to string
    #    kstring = json.dumps(kwargs)
    #    client = NovaPoshtaApi(api_key=self.api_key)
    #    warehouses = client.address.get_warehouses()
    #    frappe.throw(warehouses.text)
        
#     def get_available_services(self, **kwargs):
#         print(kwargs)
#         # kwargs to string
#         kstring = json.dumps(kwargs)
#         client = NovaPoshtaApi(api_key=self.api_key)
#         cities = client.address.get_cities()
#         frappe.throw(cities.text)
        
#         pickup_address = kwargs['pickup_address']
#         delivery_address = kwargs['delivery_address']
        
#         frappe.throw(kstring)
#         # Retrieve rates at PackLink from specification stated.
#         parcel_list = self.get_parcel_list(json.loads(kwargs))
#         shipment_parcel_params = self.get_formatted_parcel_params(parcel_list)
#         url = self.get_formatted_request_url(pickup_address, delivery_address, shipment_parcel_params)

#         if not self.api_key or not self.enabled:
#             return []

#         try:
#             responses = requests.get(url, headers={'Authorization': self.api_key})
#             responses_dict = json.loads(responses.text)
#             # If an error occured on the api. Show the error message
#             if 'messages' in responses_dict:
#                 error_message = str(responses_dict['messages'][0]['message'])
#                 frappe.throw(error_message, title=_("PackLink"))

#             available_services = []
#             for response in responses_dict:
#                 # display services only if available on pickup date
#                 if self.parse_pickup_date(pickup_date) in response['available_dates'].keys():
#                     available_service = self.get_service_dict(response)
#                     available_services.append(available_service)

#             if responses_dict and not available_services:
#                 # got a response but no service available for given date
#                 frappe.throw(_("No Services available for {0}").format(pickup_date), title=_("PackLink"))

#             return available_services
#         except Exception:
#             show_error_alert("fetching Packlink prices")

#         return []

#     # in NovaPoshtaUtils module
# class NovaPoshtaUtils:  
    
#     def get_available_services(self, pickup_from_type, delivery_to_type, pickup_address, delivery_address, shipment_parcel):
#         # Get available services from Nova Poshta.
#         if not pickup_from_type or not delivery_to_type:
#             return []

#         if pickup_from_type == 'Warehouse' and delivery_to_type == 'Warehouse':
#             return [NOVAPOSHTA_PROVIDER]

#         return []
        
        
#     def delivery_to_type(self):
#         return 'Warehouse'
        
            
#     def create_shipmentt(self, shipment, shipment_parcel):
#         # Create shipment at Nova Poshta from specification stated.
#         if not self.enabled or not self.api_key or not self.api_id:
#             return []

#         try:
#             url = self.api_endpoint
#             headers = {'content-type': 'application/json'}
#             data = {
#                 "apiKey": self.api_key,
#                 "modelName": "InternetDocument",
#                 "calledMethod": "save",
#                 "methodProperties": {
#                     "NewAddress": 1,
#                     "PayerType": "Sender",
#                     "PaymentMethod": "Cash",
#                     "DateTime": "2020-04-30T00:00:00",
#                     "CargoType": "Cargo",
#                     "VolumeGeneral": "0.0004",
#                     "Weight": shipment_parcel.weight,
#                     "ServiceType": "WarehouseWarehouse",
#                     "SeatsAmount": "1",
#                     "Description": "Documents",
#                     "Cost": shipment_parcel.cost,
#                     "CitySender": frappe.db.get_value('Address', shipment.sender_address, 'city'),
#                     "Sender": frappe.db.get_value('Address', shipment.sender_address, 'warehouse'),
#                     "SenderAddress": frappe.db.get_value('Address', shipment.sender_address, 'warehouse_address'),
#                     "ContactSender": frappe.db.get_value('Address', shipment.sender_address, 'contact_person'),
#                     "SendersPhone": frappe.db.get_value('Address', shipment.sender_address, 'phone'),
#                     "CityRecipient": frappe.db.get_value('Address', shipment_parcel.recipient_address, 'city'),
#                     "Recipient": frappe.db.get_value('Address', shipment_parcel.recipient_address, 'warehouse'),
#                     "RecipientAddress": frappe.db.get_value('Address', shipment_parcel.recipient_address, 'warehouse_address'),
#                     "ContactRecipient": frappe.db.get_value('Address', shipment_parcel.recipient_address, 'contact_person'),
#                     "RecipientsPhone": frappe.db.get_value('Address', shipment_parcel.recipient_address, 'phone')
#                 }
#             }
#             response = requests.post(url, data=json.dumps(data), headers=headers)
#             if response.status_code == 200:
#                 response = response.json()
#                 if response['success']:
#                     return response['data']
#                 else:
#                     frappe.throw(response['errors'])
#             else:
#                 frappe.throw(response.text)
#         except Exception as e:
#             frappe.throw(e)
            
#     def get_lable(self, shipment, shipment_parcel):
#         # Create shipment at Nova Poshta from specification stated.
#         if not self.enabled or not self.api_key or not self.api_id:
#             return []

#         try:
#             url = self.api_endpoint
#             headers = {'content-type': 'application/json'}
#             data = {
#                 "apiKey": self.api_key,
#                 "modelName": "InternetDocument",
#                 "calledMethod": "printDocument",
#                 "methodProperties": {
#                     "DocumentRefs": [
#                         shipment_parcel.novaposhta_id
#                     ]
#                 }
#             }
#             response = requests.post(url, data=json.dumps(data), headers=headers)
#             if response.status_code == 200:
#                 response = response.json()
#                 if response['success']:
#                     return response['data']
#                 else:
#                     frappe.throw(response['errors'])
#             else:
#                 frappe.throw(response.text)
#         except Exception as e:
#             frappe.throw(e)
            
#     def get_formatted_request_url(request):
#             """
#             Returns formatted request url.
#             """
#             return '{0}?{1}'.format(requests.request.url, requests.request.body)
       
#     def get_cities(self):
#         """
#         Returns all cities.
#         """
#         # call api by using corresponding models
#         client = NovaPoshtaApi(api_key=self.api_key)
#         cities = client.address.get_cities()
#         # models can be accessed as client properties
#         print(cities.json())
#         return cities.json()
    
#     def get_warehouses(self, city): 
#         client = NovaPoshtaApi(api_key=self.api_key)
#         warehouses = client.address.get_warehouses(city_ref=city)
#         # models can be accessed as client properties
#         print(warehouses.json())
#         return warehouses.json()
    
#     def get_delicery_to_type(self):
#         """
#         Returns all cities.
#         """
#         # call api by using corresponding models
#         client = NovaPoshtaApi(api_key=self.api_key)
#         cities = client.address.get_cities()
#         # models can be accessed as client properties
#         print(cities.json())
#         return cities.json()
    





#     def get_areas(self):
#         """
#         Returns all areas.
#         """
#         # call api by using corresponding models
#         client = NovaPoshtaApi(api_key=self.api_key)
#         areas = client.address.get_areas()  # models can be accessed as client properties
#         print(areas.json())
#         return areas.json()


