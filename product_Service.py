from flask import jsonify
from collections import defaultdict
from odoo_Service import OdooService
class ProductService (OdooService):
        

    
    def add_product(self,id, location_id):
        try:
            # Buscar el producto correspondiente
            product_data = self.models.execute_kw(
                self.self.db, self.uid, self.password,
                "product.product", "search_read",
                [[["id", "=", id]]],  # Buscar por id del producto
                {"fields": ["name", "default_code"], "limit": 1}
            )
            
            if not product_data:
                return jsonify({"error": "Producto no encontrado"})
            
            # Crear la unidad del producto en la ubicación
            product = product_data[0]
            self.models.execute_kw(
                self.self.db, self.uid, self.password,
                "stock.quant", "create",
                [{"product_id": id, "location_id": location_id, "quantity": 1}]
            )
            return jsonify({"message": f"Producto {product['name']} agregado a la ubicación {location_id}."}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500


    def search_product(self,search_term):
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
                    lot_name_results = self.models.execute_kw(
                        self.self.db, self.uid, self.password,
                        'stock.lot', 'search_read',
                        [[['name', '=', str(search_number)], ['x_studio_ficha_tcnica.name', 'ilike', base_term]]],
                        {'fields': ['name', 'x_studio_ficha_tcnica', 'x_studio_codigo_de_barras_base'], 'limit': 15}
                    )
                    results.extend(lot_name_results)
                except ValueError:
                    pass

            # General search by x_studio_ficha_tcnica.name
            general_results = self.models.execute_kw(
                self.db, self.uid, self.password,
                'stock.lot', 'search_read',
                [[['x_studio_ficha_tcnica.name', 'ilike', search_term]]],
                {'fields': ['name', 'x_studio_ficha_tcnica', 'x_studio_codigo_de_barras_base'], 'limit': 15}
            )
            results.extend(general_results)

            # Search by x_studio_codigo_de_barras_base
            barcode_results = self.models.execute_kw(
                self.db, self.uid, self.password,
                'stock.lot', 'search_read',
                [[['x_studio_codigo_de_barras_base', 'ilike', search_term]]],
                {'fields': ['name', 'x_studio_ficha_tcnica', 'x_studio_codigo_de_barras_base'], 'limit': 15}
            )
            results.extend(barcode_results)

            # Remove duplicates and limit to 15 results total
            unique_results = {r['id']: r for r in results}.values()
            final_results = list(unique_results)[:15]

            return jsonify({'results': final_results}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500


    def get_product_info(self,codebar):
        


        def fetch_product_data(codebar):
            return self.models.execute_kw(
                self.db, self.uid, self.password,
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
            variant_info = self.models.execute_kw(
                self.db, self.uid, self.password,
                'product.attribute.value', 'search_read',
                [[['id', '=', variant_id]]],
                {'fields': ['name']}
            )
            return variant_info[0].get('name')

        def fetch_product_template(template_id):
            return self.models.execute_kw(
                self.db, self.uid, self.password,
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
            quants = self.models.execute_kw(
                self.db, self.uid, self.password,
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
            traceability_data = self.models.execute_kw(
                self.db, self.uid, self.password,
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

