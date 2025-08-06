def calculate_risk_reward(entry, stop_loss, take_profit):
  risk = abs(entry - stop_loss)
  reward = abs(take_profit - entry)
  return reward / risk if risk != 0 else 0

def format_price(price):
  """Адаптивное форматирование цены в зависимости от её величины"""
  if price < 0.01:
    return f"${price:.8f}"
  elif price < 1.0:
    return f"${price:.5f}"
  elif price < 100.0:
    return f"${price:.3f}"
  elif price < 1000.0:
    return f"${price:.2f}"
  else:
    return f"${price:,.1f}"

def format_signal(symbol, current_price, direction, entry_price, stop_loss, take_profit, stop_loss_pct, take_profit_pct, risk_reward, cancel_price, warning, sma_50, sma_200, support, resistance):
  direction_emoji = "📈" if direction == "Long" else "📉"

  # Исправляем расчет процентов для корректного отображения
  if direction == "Long":
    stop_loss_pct_display = stop_loss_pct  # Уже отрицательный
    take_profit_pct_display = take_profit_pct  # Уже положительный
  else:  # Short
    # Для шорта: стоп-лосс (убыток) должен быть с минусом, тейк-профит (прибыль) с плюсом
    stop_loss_pct_display = -abs(stop_loss_pct)  # Принудительно делаем отрицательным
    take_profit_pct_display = abs(take_profit_pct)  # Принудительно делаем положительным

  # Формируем честное пояснение на основе реальной логики без "Long:" и "Short:"
  trend = "восходящий тренд" if sma_50 > sma_200 else "нисходящий тренд"
  level = f"поддержки {format_price(support)}" if direction == "Long" else f"сопротивления {format_price(resistance)}"
  explanation = f"{trend}, вход от {level}"

  signal_text = f"""
{direction_emoji} *{symbol}*

💲 *Текущая цена:* {format_price(current_price)}
📊 *Направление:* {direction}
🎯 *Точка входа:* {format_price(entry_price)} (лимитный ордер)
🛑 *Стоп-лосс:* {format_price(stop_loss)} ({stop_loss_pct_display:+.2f}%)
💎 *Тейк-профит:* {format_price(take_profit)} ({take_profit_pct_display:+.2f}%)
⚖️ *Риск/Прибыль:* 1:{risk_reward:.1f}
💡 *Пояснение:* {explanation}
❌ *Условия отмены:* Пробой {format_price(cancel_price)}
"""

  if warning:
      signal_text += f"\n⚠️ {warning}"

  return signal_text