from flask_cors import CORS, cross_origin
import xmlrpc.client
import qrcode
from flask import Flask, jsonify, request, send_file
from io import BytesIO
from collections import defaultdict

import os

import json
#passwordProduction
#passwordDev

# base_dir = os.path.dirname(os.path.abspath(__file__))  # Directorio base del proyecto
# config_path = os.path.join(base_dir,  'passwordDev.json')
# print(base_dir)

# # Cargar el archivo JSON
# with open(config_path, 'r') as file:
#     config = json.load(file)

# # Acceso a las variables
# url = config["url"]
# db = config["db"]
# username = config["username"]
# password = config["password"]

url= "https://a-codigo-barras-v2.odoo.com"
db= "a-codigo-barras-v2"
username= "info@cenat.ac.cr"
password= "123"




# Autenticación a Odoo
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})

if not uid:
    raise Exception("No se pudo autenticar con Odoo")

# Conexión al modelo
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

# Crear la aplicación Flask
app = Flask(__name__)

CORS(app) # allow CORS for all domains on all routes.

# Endpoint para agregar producto
@app.route('/addProduct/<int:id>/<int:location_id>', methods=['GET'])
def add_product(id, location_id):
    try:
        # Buscar el producto correspondiente
        product_data = models.execute_kw(
            db, uid, password,
            "product.product", "search_read",
            [[["id", "=", id]]],  # Buscar por id del producto
            {"fields": ["name", "default_code"], "limit": 1}
        )
        
        if not product_data:
            return jsonify({"error": "Producto no encontrado"})
        
        # Crear la unidad del producto en la ubicación
        product = product_data[0]
        models.execute_kw(
            db, uid, password,
            "stock.quant", "create",
            [{"product_id": id, "location_id": location_id, "quantity": 1}]
        )
        return jsonify({"message": f"Producto {product['name']} agregado a la ubicación {location_id}."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint para descartar producto por número de serie


@app.route('/transfers', methods=['POST'])
def relocate_products_by_barcodes():
    try:
        # Leer el cuerpo de la solicitud
        data = request.get_json()
        location_barcode = data.get("location-barcode")
        product_barcodes = data.get("products-codes")

        if not location_barcode or not product_barcodes:
            return jsonify({"error": "Se requiere el código de barras de la ubicación y la lista de productos"})

        # Buscar la ubicación de destino por código de barras
        location_data = models.execute_kw(
            db, uid, password,
            "stock.location", "search_read",
            [[["barcode", "=", location_barcode]]],
            {"fields": ["id"]}
        )

        if not location_data:
            return jsonify({"error": f"Ubicación con código de barras {location_barcode} no encontrada"})
        
        destination_location_id = location_data[0]["id"]
        print(f"Destination Location ID: {destination_location_id}")

        # Buscar los productos por sus códigos de barras en stock.lot (con lot_id)
        quants = models.execute_kw(
            db, uid, password,
            "stock.quant", "search_read",
            [[["lot_id.x_studio_codigo_de_barra_de_la_instancia", "in", product_barcodes]]],
            {"fields": ["id", "product_id", "inventory_quantity_auto_apply", "location_id", "lot_id"]}
        )

        if not quants:
            return jsonify({"error": "No se encontraron productos con los códigos de barras proporcionados en la ubicación indicada"})

        # Determinar la ubicación de origen a partir de la quant
        source_location_id = quants[0]["location_id"]
        print(f"Source Location ID: {source_location_id}")

        # Crear una transacción de reubicación utilizando stock.quant.relocate
        relocate = models.execute_kw(
            db, uid, password,
            "stock.quant.relocate", "create",
            [{
                "dest_location_id": destination_location_id,
                "quant_ids": [[6, 0, [quant["id"] for quant in quants]]]
            }]
        )

        print(f"Relocation created: {relocate}")

        # Ejecutar la acción de reubicación
        models.execute_kw(
            db, uid, password,
            "stock.quant.relocate", "action_relocate_quants",
            [[relocate]]
        )

        # Realizar un "refresh" de las quants después de la acción de reubicación
        # Esto asegura que las quants vacías (con cantidad cero) sean reconocidas correctamente
        updated_quants = models.execute_kw(
            db, uid, password,
            "stock.quant", "search_read",
            [[["lot_id.x_studio_codigo_de_barra_de_la_instancia", "in", product_barcodes]]],
            {"fields": ["id", "inventory_quantity_auto_apply", "location_id", "lot_id"]}
        )

        # Buscar y eliminar quants con cantidad cero en la ubicación de origen
        for quant in updated_quants:
            if quant["inventory_quantity_auto_apply"] == 0:
                models.execute_kw(
                    db, uid, password,
                    "stock.quant", "unlink",
                    [[quant["id"]]]
                )
                print(f"Quant with serial {quant['lot_id']} removed from source location.")

            # Extraer el lot_id de la lista si es necesario
            lot_id = quant["lot_id"]
            if isinstance(lot_id, list):
                lot_id = lot_id[0]  # Usar solo el primer valor de la lista

            # Actualizar la ubicación del lote
            models.execute_kw(
                db, uid, password,
                "stock.lot", "write",
                [[lot_id], {"location_id": destination_location_id}]
            )
            print(f"Lot {lot_id} location updated to {destination_location_id}.")
        return jsonify({"message": "Productos reubicados exitosamente, y quants vacíos eliminados."})

    except Exception as e:
        return jsonify({"error": str(e)})





@app.route('/QR_addProduct/<int:id>/<int:location_id>', methods=['GET'])
def qr_add_product(id, location_id):
    url = f"http://localhost:8080/addProduct/{id}/{location_id}"
    img = qrcode.make(url)
    
    # Guardar el código QR en memoria
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    
    return send_file(img_io, mimetype='image/png', as_attachment=True, download_name="qr_addProduct.png")




# Datos de ejemplo
scan_products = [
    {
        'codebar': '130',
        'name': 'A-pinedo',
        'presentation': '250 ml',
        'serialNumber': '356',
        'securityDatasheet': 'https://google.com',
    }
]





def fetch_product_data(codebar):
    return models.execute_kw(
        db, uid, password,
        'stock.lot', 'search_read',
        [[['x_studio_codigo_de_barra_de_la_instancia', '=', codebar]]],
        {'fields': [
            'x_studio_codigo_de_barra_de_la_instancia',
            'x_studio_ficha_de_seguridad',
            'name',
            'x_studio_presentation',
            'x_studio_nombre',
            'location_id',
            'x_studio_estado',
            'company_id',
            'x_studio_ficha_tcnica',
            'x_studio_laboratorio',
            'x_studio_variantes_product',
            'x_studio_trazabilidad',
        ]}
    )

def fetch_variant_name(variant_id):
    variant_info = models.execute_kw(
        db, uid, password,
        'product.attribute.value', 'search_read',
        [[['id', '=', variant_id]]],
        {'fields': ['name']}
    )
    return variant_info[0].get('name')

def fetch_product_template(template_id):
    return models.execute_kw(
        db, uid, password,
        'product.template', 'search_read',
        [[['id', '=', template_id]]],
        {'fields': [
            'x_studio_descripcin_n_cas',
            'x_studio_codigo_base',
            'x_studio_uso_comn',
            'x_studio_clasificacion_de_peligro_gsa',
        ]}
    )[0]

def fetch_stock_by_variant(template_id):
    quants = models.execute_kw(
        db, uid, password,
        'stock.quant', 'search_read',
        [[['product_tmpl_id', '=', template_id], ['quantity', '>', 0]]],
        {'fields': ['product_id', 'location_id']}
    )
    stock_by_variant = {}
    quantPerVariant = defaultdict(list)
    
    for quant in quants:
        product_id = quant['product_id'][1]  # Nombre de la variante
        quantity = 1
        stock_by_variant[product_id] = stock_by_variant.get(product_id, 0) + quantity
        quantPerVariant[product_id].append(quant['location_id'][1])
    
    
    # Agrupar ubicaciones y contar
    for variant_name in quantPerVariant:
        location_counts = defaultdict(int)
        for location in quantPerVariant[variant_name]:
            location_counts[location] += 1
        quantPerVariant[variant_name] = location_counts

    # Crear la estructura final
    return [
        {
            'variation': variant_name,
            'count': qty,
            'stock': [{'location': loc, 'count': count} for loc, count in quantPerVariant[variant_name].items()]
        }
        for variant_name, qty in stock_by_variant.items()
    ]

def fetch_traceability(traceability_ids):
    traceability_data = models.execute_kw(
        db, uid, password,
        'stock.move.line', 'search_read',
        [[['id', 'in', traceability_ids], ['qty_done', '>', 0]]],
        {'fields': ['location_dest_id', 'date'], 'limit': 15, 'order': 'date desc'}
    )
    return [
        {
            'date': record['date'],
            'location_dest_id': record['location_dest_id'][1]  # Solo la dirección
        }
        for record in traceability_data
    ]

def build_response(product, variant, product_template, stock_response, traceability_data):
    
    
    print(product)
    print("=========================================")
    print(variant)
    print("=========================================")
    print(product_template )
    print("=========================================")
    print(stock_response)
    print("=========================================")
    print(traceability_data)
    print("=========================================")
    
    
    return {
        'x_studio_laboratorio': "Sin asignar" if not product.get('x_studio_laboratorio') else product.get('x_studio_laboratorio')[1],

        'x_studio_descripcin_n_cas': product_template.get('x_studio_descripcin_n_cas'),
        'x_studio_codigo_base': product_template.get('x_studio_codigo_base'),
        'x_studio_uso_comn': product_template.get('x_studio_uso_comn'),
        'codebar': product.get('x_studio_codigo_de_barra_de_la_instancia'),
        'securityDatasheet': product.get('x_studio_ficha_de_seguridad'),
        'serialNumber': product.get('name'),
        'presentation': variant,
        'name': product.get('x_studio_nombre'),
        'location_id': product.get('location_id'),
        'x_studio_estado': product.get('x_studio_estado'),
        'x_studio_trazabilidad': traceability_data,

        'x_studio_clasificacion_de_peligro_gsa': product_template.get('x_studio_clasificacion_de_peligro_gsa'),
        'stockByVariant': stock_response
    }

@app.route('/get-products/<string:codebar>', methods=['GET'])
def get_product_info(codebar):
    try:
        product_data = fetch_product_data(codebar)
        if not product_data:
            return jsonify({'error': 'Producto no encontrado', 'desc': 'El artículo no se encuentra en la base de datos'})

        product = product_data[0]
    
        variant = product.get('x_studio_presentation') or fetch_variant_name(product.get('x_studio_variantes_product')[0])
    
        product_template_id = product.get("x_studio_ficha_tcnica")[0]
    
        product_template = fetch_product_template(product_template_id)
    
        stock_response = fetch_stock_by_variant(product_template_id)
    
        traceability_data = fetch_traceability(product.get('x_studio_trazabilidad'))
    

        response = build_response(product, variant, product_template, stock_response, traceability_data)
        print(response)
        return jsonify(response), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500







@app.route('/get-locations/<string:codebar>', methods=['GET'])
def get_location_info(codebar):
    try:
        # Buscar la ubicación por código de barras en `stock.location`
        location_data = models.execute_kw(
            db, uid, password,
            "stock.location", "search_read",
            [[["barcode", "=", codebar]]],
            {"fields": ["name", "x_studio_tipo_de_ubicacin", "barcode", "location_id", "id"]}
        )

        if not location_data:
            return jsonify({"error": f"Ubicación con código de barras {codebar} no encontrada"})

        location = location_data[0]  # Asumimos que el código de barras es único
        location_id = location["id"]

        # Buscar productos en `stock.lot` relacionados con esta ubicación
        lots_data = models.execute_kw(
            db, uid, password,
            "stock.lot", "search_read",
            [[["quant_ids.location_id", "=", location_id]]],
            {"fields": [
                "x_studio_codigo_de_barra_de_la_instancia",
                "x_studio_ficha_de_seguridad",
                "name",
                "x_studio_presentation",
                "x_studio_nombre",
                "quant_ids"
            ]}
        )

        # Filtrar y formatear los productos que tienen cantidades mayores a cero
        products = []
        for lot in lots_data:
            quant_ids = lot.get("quant_ids", [])
            if quant_ids:
                quants_data = models.execute_kw(
                    db, uid, password,
                    "stock.quant", "search_read",
                    [[["id", "in", quant_ids], ["quantity", ">", 0]]],
                    {"fields": ["id", "quantity"]}
                )

                if quants_data:
                    products.append({
                        "codebar": lot.get("x_studio_codigo_de_barra_de_la_instancia"),
                        "securityDatasheet": lot.get("x_studio_ficha_de_seguridad"),
                        "serialNumber": lot.get("name"),
                        "presentation": lot.get("x_studio_presentation"),
                        "name": lot.get("x_studio_nombre")
                    })

        # Construir la respuesta con la ubicación y los productos en ella
        response = {
            "location": {
                "name": location.get("name"),
                "type": location.get("x_studio_tipo_de_ubicacin"),
                "barcode": location.get("barcode"),
                "parent_location_id": location.get("location_id"),
                "id": location_id
            },
            "products": products
        }

        return jsonify(response)
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route('/get-users/<string:codebar>', methods=['GET'])
def get_user_info(codebar):
    # Función para el prefijo "usu-"
    if codebar.startswith('usu-'):
        codebar = codebar[4:]  # Eliminar el prefijo "usu-"
        # Lógica de búsqueda para los usuarios
        return jsonify({'user': f'Usuario {codebar}'})
    else:
        return jsonify({'error': 'Prefijo incorrecto para usuarios'}), 400


@app.route('/get-actions/<string:codebar>', methods=['GET'])
def get_action_info(codebar):
    # Función para el prefijo "acc-"
    if codebar.startswith('acc-'):
        codebar = codebar[4:]  # Eliminar el prefijo "acc-"
        # Lógica de búsqueda para las acciones
        return jsonify({'action': f'Acción {codebar}'})
    else:
        return jsonify({'error': 'Prefijo incorrecto para acciones'}), 400


@app.route('/process-scan-error', methods=['POST'])
def process_scan_error():
    # Esta función es un lugar para manejar errores genéricos, puede tomar parámetros desde el cuerpo de la solicitud.
    # Aquí, simplemente retornamos un error genérico.
    return jsonify({'error': 'Error al procesar el código'}), 500

@app.route("/test",methods=['GET'])
def test():
      return jsonify({'user': f'Usuario 123'})


@app.route('/dbtest', methods=['GET'])
def doConecctionTest():
    print("hola mundo")
    try:
        # Buscar en el modelo `stock.lot` con el campo `x_studio_codigo_de_barra_de_la_instancia`
        product_data = models.execute_kw(
            db, uid, password,
            'stock.lot', 'search_read',
            [[]],
            {'fields': [
                
                
                'name',
                
                'x_studio_nombre',
                'location_id',
                
            ]}
        )
        print(product_data)
        if not product_data:
            return jsonify({'error': 'Producto no encontrado', 'desc': 'El artículo no se encuentra en la base de datos'})

        # Procesar el resultado y construir el JSON
        product = product_data[0]  # Solo devolvemos el primer resultado
        print(product)
        response = {
            'codebar': product.get('x_studio_codigo_de_barra_de_la_instancia'),
            'securityDatasheet': product.get('x_studio_ficha_de_seguridad'),
            'serialNumber': product.get('name'),
            'presentation': product.get('x_studio_presentation'),
            'name': product.get('x_studio_nombre'),
            'location_id': product.get('location_id')
        }

        return jsonify(response), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500




@app.route('/search_Product/<string:search_term>', methods=['GET'])
def search_product(search_term):
    try:
        search_conditions = [['x_studio_ficha_tcnica.name', 'ilike', search_term]]
        results = []

        # Detect sequence with "- int"
        if '-' in search_term:
            term_parts = search_term.rsplit('-', 1)
            base_term = term_parts[0].strip()
            try:
                search_number = int(term_parts[1].strip())
                # Search for lot.name == number
                lot_name_results = models.execute_kw(
                    db, uid, password,
                    'stock.lot', 'search_read',
                    [[['name', '=', str(search_number)], ['x_studio_ficha_tcnica.name', 'ilike', base_term]]],
                    {'fields': ['name', 'x_studio_ficha_tcnica', 'x_studio_codigo_de_barras_base'], 'limit': 15}
                )
                results.extend(lot_name_results)
            except ValueError:
                pass

        # General search by x_studio_ficha_tcnica.name
        general_results = models.execute_kw(
            db, uid, password,
            'stock.lot', 'search_read',
            [[['x_studio_ficha_tcnica.name', 'ilike', search_term]]],
            {'fields': ['name', 'x_studio_ficha_tcnica', 'x_studio_codigo_de_barras_base'], 'limit': 15}
        )
        results.extend(general_results)

        # Search by x_studio_codigo_de_barras_base
        barcode_results = models.execute_kw(
            db, uid, password,
            'stock.lot', 'search_read',
            [[['x_studio_codigo_de_barras_base', 'ilike', search_term]]],
            {'fields': ['name', 'x_studio_ficha_tcnica', 'x_studio_codigo_de_barras_base'], 'limit': 15}
        )
        results.extend(barcode_results)

        # Remove duplicates and limit to 15 results total
        unique_results = {r['id']: r for r in results}.values()
        final_results = list(unique_results)[:15]

        # Search in product.template for products without stock
        no_stock_results = []
        product_template_results = models.execute_kw(
            db, uid, password,
            'product.template', 'search_read',
            [[['name', 'ilike', search_term]]],
            {'fields': ['id', 'name']}
        )

        for product in product_template_results:
            # Check for quantities in stock.quant
            stock_quant_results = models.execute_kw(
                db, uid, password,
                'stock.quant', 'search_read',
                [[['product_tmpl_id', '=', product['id']], ['quantity', '>', 0]]],
                {'fields': ['quantity']}
            )
            if not stock_quant_results:  # No stock found
                no_stock_results.append({'id': product['id'], 'name': product['name'], 'quantity': 0})

        return jsonify({'results': final_results, 'no_stock_products': no_stock_results}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500



@app.route('/fetch_user', methods=['POST'])
def fetch_user():
    try:
        data = request.get_json()
        barcode = data.get('barcode')
        if not barcode:
            return jsonify({'error': 'No barcode provided'}), 400

        # Search for employee by barcode
        employee_data = models.execute_kw(
            db, uid, password,
            'hr.employee', 'search_read',
            [[['barcode', '=', barcode]]],
            {'fields': ['name','id']}
        )

        if not employee_data:
            return jsonify({'error': 'Employee not found'}), 404

        employee = employee_data[0]
        return jsonify({'name': employee['name'], 'id':employee['id']}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500











# Iniciar la aplicación Flask
if __name__ == '__main__':
    app.run(host="0.0.0.0" ,port="8090")
