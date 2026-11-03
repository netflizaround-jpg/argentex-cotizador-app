"""Motor puro de costos de Argentex. Sin acceso a red ni base de datos."""
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING
from urllib.parse import urlparse


def D(value, default='0'):
    if value is None or value == '':
        value = default
    return Decimal(str(value))


def money(value):
    return float(D(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def upward_step(value, step):
    step = D(step)
    if step <= 0:
        raise ValueError('El redondeo debe ser positivo.')
    return int((D(value) / step).to_integral_value(rounding=ROUND_CEILING) * step)


def classify_market(e):
    host = (urlparse(e.get('source_url') or '').hostname or '').lower()
    is_ml = host == 'mercadolibre.com.ar' or host.endswith('.mercadolibre.com.ar')
    verified = bool(e.get('same_sku')) and bool(e.get('brand_new')) and bool(e.get('original')) and bool(e.get('in_stock')) and bool(e.get('reputation_ok')) and bool(e.get('payment_verified')) and bool(e.get('shipping_verified'))
    return is_ml, verified


def calculate_order(order, settings, fx=None):
    items = order.get('items', [])
    rates = settings['rates_usd_kg']
    fields = {'qty', 'unit_price_usd', 'unit_weight_g'}
    problems = []
    item_subtotal = D('0')
    total_item_g = D('0')
    shipping = D('0')
    market_ars = D('0')
    market_complete = bool(items)
    market_competitors = []
    total_market_verified = 0
    total_ml = 0
    item_views = []
    for item in items:
        qty = D(item.get('qty', 1))
        price = D(item.get('unit_price_usd'))
        weight = D(item.get('unit_weight_g'))
        if qty <= 0 or qty != int(qty):
            problems.append(f"Cantidad inválida: {item.get('name', 'producto')}")
        if price < 0: problems.append(f"Precio negativo: {item.get('name', 'producto')}")
        if price == 0: problems.append(f"Falta precio de compra: {item.get('name', 'producto')}")
        if weight <= 0: problems.append(f"Falta peso con caja y accesorios: {item.get('name', 'producto')}")
        if item.get('category') not in rates: problems.append('Categoría sin tarifa configurada')
        item_subtotal += max(price, D(0)) * max(qty, D(0))
        total_item_g += max(weight, D(0)) * max(qty, D(0))
        evidences = []
        for e in item.get('market', []):
            is_ml, verified = classify_market(e)
            if verified and D(e.get('price_ars')) > 0:
                delivered = D(e.get('price_ars')) + D(e.get('shipping_ars'))
                evidences.append((delivered, e))
                total_market_verified += 1
                if is_ml: total_ml += 1
                market_competitors.append(e.get('source_name', 'Tienda'))
        if evidences:
            minimum, source = min(evidences, key=lambda x:x[0])
            market_ars += minimum * qty
            cheapest = {'source':source.get('source_name'), 'price_ars_with_shipping':money(minimum), 'url':source.get('source_url')}
        else:
            market_complete = False
            cheapest = None
        item_views.append({'id':item.get('id'), 'name':item.get('name'), 'cheapest_market':cheapest, 'shipping_usd':None})
    base_g = total_item_g + max(D(order.get('outer_packaging_g')), D(0))
    buffer_g = max(base_g * D(settings['weight_protection_pct']) / 100, D(settings['min_protection_g'])) if items and total_item_g>0 else D(0)
    final_g = upward_step(base_g + buffer_g, settings['rounding_g']) if items and total_item_g > 0 else 0
    weight_complete = bool(items) and total_item_g > 0 and all(D(i.get('unit_weight_g'))>0 for i in items)
    if weight_complete:
        for idx, item in enumerate(items):
            share = D(final_g) * D(item['unit_weight_g']) * D(item['qty']) / total_item_g
            fee = share * D(rates[item['category']]) / 1000
            shipping += fee
            item_views[idx]['shipping_usd'] = money(fee)
    else:
        shipping = None
    internal = None
    if final_g and weight_complete:
        if final_g <= D(settings['internal_shipping_limit_kg']) * 1000:
            internal = D(settings['internal_shipping_usd'])
        elif order.get('us_shipping_override') is not None and order.get('us_shipping_override') != '':
            internal = D(order.get('us_shipping_override'))
        else:
            problems.append('Pedido de más de 5 kg: definir envío interno de EE. UU.')
    tax_mode = order.get('tax_mode', 'not_applicable')
    tax_rate = D(order.get('tax_rate'))
    if tax_mode == 'apply':
        if tax_rate < 0 or tax_rate > 100: problems.append('Tasa de impuesto inválida')
        us_taxes = item_subtotal * tax_rate / 100
    elif tax_mode in ('included', 'not_applicable'):
        us_taxes = D(0)
    else:
        problems.append('Modo de impuestos no reconocido')
        us_taxes = D(0)
    extra = D(order.get('import_extra_usd'))
    if extra < 0: problems.append('Cargos adicionales no pueden ser negativos')
    cost = item_subtotal + us_taxes + shipping + internal + extra if shipping is not None and internal is not None and not problems else None
    fx_data = fx or {}
    rate = D(fx_data.get('selected_rate')) if fx_data.get('valid') else None
    market_usd = market_ars / rate if market_complete and rate and rate>0 else None
    manual_price = D(order['price_override_usd']) if order.get('price_override_usd') not in (None, '') else None
    if manual_price is not None and manual_price <= 0: problems.append('Precio manual debe ser mayor a cero')
    market_gap = market_usd - cost if (market_usd is not None and cost is not None) else None
    recommended = None
    if cost is not None and market_gap is not None and market_gap > 0:
        recommended = cost + market_gap * D(settings['capture_market_gap_pct']) / 100
    sell = manual_price if manual_price is not None else recommended
    profit = sell - cost if sell is not None and cost is not None else None
    profitability_pct = profit / cost * 100 if profit is not None and cost and cost > 0 else None
    if not items: decision = 'Agregá un producto'
    elif problems or cost is None: decision = 'Revisar costos y pesos'
    elif not rate: decision = 'Actualizar dólar blue y MEP'
    elif not market_complete: decision = 'Comparativa argentina incompleta'
    elif market_gap is not None and market_gap <= 0: decision = 'No conviene al precio mínimo de mercado'
    elif profit is not None and profit <= 0: decision = 'Venta sin rentabilidad'
    elif sell is None: decision = 'Revisar precio comercial'
    else: decision = 'Oportunidad comercial (sujeta a validación)'
    return {
        'purchase_usd': money(item_subtotal),
        'tax_usd': money(us_taxes), 'tax_mode':tax_mode,
        'international_freight_usd': money(shipping) if shipping is not None else None,
        'internal_shipping_usd':money(internal) if internal is not None else None,
        'import_extra_usd':money(extra), 'deposit_usd':0,
        'cost_usd':money(cost) if cost is not None else None,
        'item_base_g':int(total_item_g), 'outer_packaging_g':int(D(order.get('outer_packaging_g'))),
        'weight_base_g':int(base_g), 'buffer_raw_g':float(buffer_g), 'weight_billable_g':final_g if weight_complete else None,
        'weight_complete':weight_complete, 'item_breakdown':item_views,
        'market_min_ars':money(market_ars) if market_complete else None,
        'market_min_usd':money(market_usd) if market_usd is not None else None,
        'market_complete':market_complete, 'verified_offers':total_market_verified,
        'mercado_libre_offers':total_ml, 'other_store_offers':total_market_verified - total_ml,
        'market_gap_usd':money(market_gap) if market_gap is not None else None,
        'recommended_price_usd':money(recommended) if recommended is not None else None,
        'sell_price_usd':money(sell) if sell is not None else None,
        'sell_price_ars_approx':money(sell * rate) if sell is not None and rate else None,
        'profit_usd':money(profit) if profit is not None else None,
        'margin_on_cost_pct':money(profitability_pct) if profitability_pct is not None else None,
        'fx':fx_data, 'decision': decision, 'problems':problems,
        'approval_ready':bool(cost is not None and rate and not problems and market_complete and total_ml>=len(items) and (total_market_verified-total_ml)>=len(items) and sell and sell>cost),
    }
