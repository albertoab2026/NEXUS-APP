import boto3
from boto3.dynamodb.conditions import Key
from datetime import datetime, timedelta
import streamlit as st

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
tabla = dynamodb.Table('TABLA_CIERRE_V4')

def abrir_cierre(tenant_id, fecha):
    """Abre cierre. 1 por día por tenant. No duplicados."""
    try:
        tabla.put_item(
            Item={
                'TenantID': tenant_id,
                'FechaISO': fecha,
                'Estado': 'ABIERTO',
                'TotalEfectivo': 0,
                'TotalYape': 0,
                'TotalPlin': 0,
                'UsuarioTurno': st.session_state.usuario
            },
            ConditionExpression='attribute_not_exists(TenantID)'
        )
        return True
    except:
        return False # Ya existe cierre hoy

def cerrar_cierre(tenant_id, fecha, efectivo, yape, plin):
    """Cierra el día. Solo 1 update."""
    total = efectivo + yape + plin
    tabla.update_item(
        Key={'TenantID': tenant_id, 'FechaISO': fecha},
        UpdateExpression='SET Estado = :e, TotalEfectivo = :ef, TotalYape = :y, TotalPlin = :p, Total = :t',
        ExpressionAttributeValues={':e': 'CERRADO', ':ef': efectivo, ':y': yape, ':p': plin, ':t': total}
    )

def obtener_cierre(tenant_id, fecha):
    """Obtiene cierre de un día específico. Rápido, sin scan."""
    res = tabla.query(
        KeyConditionExpression=Key('TenantID').eq(tenant_id) & Key('FechaISO').eq(fecha)
    )
    return res['Items'][0] if res['Items'] else None

def obtener_historial(tenant_id, dias=30):
    """Historial de cierres. Rápido, sin scan."""
    hoy = datetime.now()
    fecha_inicio = (hoy - timedelta(days=dias)).strftime('%Y-%m-%d')
    res = tabla.query(
        KeyConditionExpression=Key('TenantID').eq(tenant_id) & Key('FechaISO').gte(fecha_inicio)
    )
    return res['Items']
