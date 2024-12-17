
from flask import jsonify
from collections import defaultdict
from odoo_Service import OdooService

class LocationService(OdooService):
    
    def relocate_products_by_barcodes(self,data):
        try:
            # Leer el cuerpo de la solicitud
            
            location_barcode = data.get("location-barcode")
            product_barcodes = data.get("products-codes")

            if not location_barcode or not product_barcodes:
                return jsonify({"error": "Se requiere el código de barras de la ubicación y la lista de productos"})

            # Buscar la ubicación de destino por código de barras
            location_data = self.models.execute_kw(
                self.db, self.uid, self.password,
                "stock.location", "search_read",
                [[["barcode", "=", location_barcode]]],
                {"fields": ["id"]}
            )

            if not location_data:
                return jsonify({"error": f"Ubicación con código de barras {location_barcode} no encontrada"})
            
            destination_location_id = location_data[0]["id"]
            print(f"Destination Location ID: {destination_location_id}")

            # Buscar los productos por sus códigos de barras en stock.lot (con lot_id)
            quants = self.models.execute_kw(
                self.db, self.uid, self.password,
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
            relocate = self.models.execute_kw(
                self.db, self.uid, self.password,
                "stock.quant.relocate", "create",
                [{
                    "dest_location_id": destination_location_id,
                    "quant_ids": [[6, 0, [quant["id"] for quant in quants]]]
                }]
            )

            print(f"Relocation created: {relocate}")

            # Ejecutar la acción de reubicación
            self.models.execute_kw(
                self.db, self.uid, self.password,
                "stock.quant.relocate", "action_relocate_quants",
                [[relocate]]
            )

            # Realizar un "refresh" de las quants después de la acción de reubicación
            # Esto asegura que las quants vacías (con cantidad cero) sean reconocidas correctamente
            updated_quants = self.models.execute_kw(
                self.db, self.uid, self.password,
                "stock.quant", "search_read",
                [[["lot_id.x_studio_codigo_de_barra_de_la_instancia", "in", product_barcodes]]],
                {"fields": ["id", "inventory_quantity_auto_apply", "location_id", "lot_id"]}
            )

            # Buscar y eliminar quants con cantidad cero en la ubicación de origen
            for quant in updated_quants:
                if quant["inventory_quantity_auto_apply"] == 0:
                    self.models.execute_kw(
                        self.db, self.uid, self.password,
                        "stock.quant", "unlink",
                        [[quant["id"]]]
                    )
                    print(f"Quant with serial {quant['lot_id']} removed from source location.")

                # Extraer el lot_id de la lista si es necesario
                lot_id = quant["lot_id"]
                if isinstance(lot_id, list):
                    lot_id = lot_id[0]  # Usar solo el primer valor de la lista

                # Actualizar la ubicación del lote
                self.models.execute_kw(
                    self.db, self.uid, self.password,
                    "stock.lot", "write",
                    [[lot_id], {"location_id": destination_location_id}]
                )
                print(f"Lot {lot_id} location updated to {destination_location_id}.")
            return jsonify({"message": "Productos reubicados exitosamente, y quants vacíos eliminados."})

        except Exception as e:
            return jsonify({"error": str(e)})



    def get_location_info(self,codebar):
        try:
            # Buscar la ubicación por código de barras en `stock.location`
            location_data = self.models.execute_kw(
                self.db, self.uid, self.password,
                "stock.location", "search_read",
                [[["barcode", "=", codebar]]],
                {"fields": ["name", "x_studio_tipo_de_ubicacin", "barcode", "location_id", "id"]}
            )

            if not location_data:
                return jsonify({"error": f"Ubicación con código de barras {codebar} no encontrada"})

            location = location_data[0]  # Asumimos que el código de barras es único
            location_id = location["id"]

            # Buscar productos en `stock.lot` relacionados con esta ubicación
            lots_data = self.models.execute_kw(
                self.db, self.uid, self.password,
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
                    quants_data = self.models.execute_kw(
                        self.db, self.uid, self.password,
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

