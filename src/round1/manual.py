
conversions = {
  'snowball-pizza':1.45,
  'snowball-nugget':.52,
  'snowball-shell':.72,
  'pizza-snowball':.7,
  'pizza-nugget':.31,
  'pizza-shell':.48,
  'nugget-snowball':1.95,
  'nugget-pizza':3.1,
  'nugget-shell':1.49,
  'shell-snowball':1.34,
  'shell-pizza':1.98,
  'shell-nugget':.64,
  'shell-shell':1.0,
  'snowball-snowball':1.0,
  'pizza-pizza':1.0,
  'nugget-nugget':1.0,
}

starting_shells = 2000

# Generate every possible combination of 5 trades
combinations = [['shell-shell']]
new_combos = []

for i in range(4):
  for combo in combinations:
    for conv in conversions.keys():
      curr_curreny = combo[-1].split('-')[-1]
      # print(f'curr_combo: {combo}, curr_curreny: {curr_curreny}, conv: {conv}, trufiy: {conv[:len(curr_curreny)] == curr_curreny}')
      if conv[:len(curr_curreny)] == curr_curreny:
        new_combos.append(combo + [conv])
  combinations = new_combos[new_combos.index(combo)+1 if combo in new_combos else 0:]

# Calculate the value of each combination
results = []
for combo in new_combos:
  value = starting_shells
  for conv in combo:
    curr_currency = conv.split('-')[0]
    next_currency = conv.split('-')[1]
    value *= conversions[curr_currency + '-' + next_currency]
  # Convert back to shells
  value *= conversions[next_currency + '-shell']
  results.append((combo, value))

# Sort and print the results
results.sort(key=lambda x: x[1], reverse=True)
for combo, value in results:
  print(combo, value)

print(f'{len(results)} combinations')