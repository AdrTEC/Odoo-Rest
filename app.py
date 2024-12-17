
from flask_cors import CORS, cross_origin
from flask import Flask, jsonify, request, send_file
from product_Service import ProductService
from location_Service import LocationService
from user_Service import UserService





# Autenticación a Odoo

# Crear la aplicación Flask
app = Flask(__name__)
CORS(app) 
product_Service= ProductService( )
location_Service= LocationService( )
user_Service= UserService( )





@app.route('/transfers', methods=['POST'])
def relocate_products_by_barcodes():
    data = request.get_json()
    return location_Service.relocate_products_by_barcodes(data)

@app.route('/get-locations/<string:codebar>', methods=['GET'])
def get_location_info(codebar):
    return location_Service.get_location_info(codebar)


@app.route('/fetch_user', methods=['POST'])
def fetch_user():
    data = request.get_json()
    return user_Service.fetch_user(data)






@app.route('/addProduct/<int:id>/<int:location_id>', methods=['GET'])
def add_product(id, location_id):
    return product_Service.add_product(id, location_id)

@app.route('/search_Product/<string:search_term>', methods=['GET'])
def search_product(search_term):
    return product_Service.search_product(search_term)

@app.route('/get-products/<string:codebar>', methods=['GET'])
def get_product_info(codebar):
    return product_Service.get_product_info(codebar)



# Iniciar la aplicación Flask
if __name__ == '__main__':
    app.run(host="0.0.0.0" ,port="8090")
