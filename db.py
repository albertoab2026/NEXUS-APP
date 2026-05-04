import boto3
import streamlit as st
from decimal import Decimal
from datetime import datetime
import pytz

@st.cache_resource
def get_dynamodb_table():
    """Conecta a DynamoDB usando secrets"""
    aws_config = st.secrets["aws"]
    dynamodb = boto3.resource(
        'dynamodb',
        aws_access_key_id=aws_config['aws_access_key_id'],
        aws_secret_access_key=aws_config['aws_secret_access_key'],
        region_name=aws_config['region_name']
    )
    return dynamodb.Table(aws_config['dynamodb_table'])

def abrir_cierre(tenant_id, fecha):
    """Abre un cierre. Solo 1 por día"""
    tabla = get_dynamodb_table()
    try:
        tabla.put_item(
            Item={
                'TenantID': tenant_id,
                'FechaISO': fecha,
                'Estado': 'ABIERTO',
                'TotalEfectivo': Decimal('0'),
                'TotalYape': Decimal('0'),
                'TotalPlin': Decimal('0')
            },
            ConditionExpression='attribute_not_exists(TenantID)'
        )
        return True
    except tabla.meta.client.exceptions.ConditionalCheckFailedException:
        return False

def cerrar_cierre(tenant_id, fecha, efectivo, yape, plin):
    """Cierra el cierre del día"""
    tabla = get_dynamodb_table()
    tabla.put_item(
        Item={
            'TenantID': tenant_id,
            'FechaISO': fecha,
            'Estado': 'CERRADO',
            'TotalEfectivo': Decimal(str(efectivo)),
            'TotalYape': Decimal(str(yape)),
            'TotalPlin': Decimal(str(plin))
        }
    )
    return True

def obtener_cierre(tenant_id, fecha):
    """Obtiene el cierre de un día"""
    tabla = get_dynamodb_table()
    response = tabla.get_item(
        Key={'TenantID': tenant_id, 'FechaISO': fecha}
    )
    return response.get('Item')

def obtener_historial(tenant_id, limite=10):
    """Obtiene los últimos cierres"""
    tabla = get_dynamodb_table()
    response = tabla.query(
        KeyConditionExpression='TenantID = :tid',
        ExpressionAttributeValues={':tid': tenant_id},
        ScanIndexForward=False,
        Limit=limite
    )
    return response.get('Items', [])

def hay_cierre_abierto(tenant_id, fecha):
    """Verifica si hay un cierre abierto hoy"""
    cierre = obtener_cierre(tenant_id, fecha)
    return cierre is not None and cierre.get('Estado') == 'ABIERTO'
