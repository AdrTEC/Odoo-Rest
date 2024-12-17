from flask import Flask, jsonify, request, send_file
from collections import defaultdict
import json
import xmlrpc.client
class OdooService:
    
    
    def __init__(self):
        # Intentar cargar los datos desde el archivo JSON
        try:
            with open("passwordDev.json", "r") as file:
                config = json.load(file)
            
            self.db = config.get("db")
            self.username = config.get("username")
            self.password = config.get("password")
            self.url= config.get("url")
            
            
            common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
            self.uid = common.authenticate(self.db, self.username, self.password, {})
            
            if not self.uid:
                raise Exception("No se pudo autenticar con Odoo")
            # Conexión al modelo
            self.models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")
        
        except FileNotFoundError:
            raise FileNotFoundError("El archivo 'passwordDev.json' no fue encontrado.")
        except json.JSONDecodeError:
            raise ValueError("El archivo 'passwordDev.json' no tiene un formato JSON válido.")
