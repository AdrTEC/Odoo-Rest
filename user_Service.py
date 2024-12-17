
from flask import jsonify
from collections import defaultdict
from odoo_Service import OdooService

class UserService(OdooService):
    
    def fetch_user(self,data):
        try:
            
            barcode = data.get('barcode')
            if not barcode:
                return jsonify({'error': 'No barcode provided'}), 400

            # Search for employee by barcode
            employee_data = self.models.execute_kw(
                self.db, self.uid, self.password,
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
