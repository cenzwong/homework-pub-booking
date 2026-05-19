base_per_head = 18
venue_mult = 1.0
party_size = 6
duration_hours = 3
subtotal = base_per_head * venue_mult * party_size * max(1, duration_hours)
service = subtotal * 10 / 100
total = subtotal + service + 0 + 200
print(f"subtotal={subtotal}, service={service}, total={total}")
