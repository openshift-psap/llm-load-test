import json
import matplotlib.pyplot as plt
import numpy as np

with open('output/output.json') as f:
    data = json.load(f)

data = data['results']

if isinstance(data[0], dict):
    response_times = []
    total_tokens = []
    throughputs = []
    for item in data:
        if 'response_time' in item and item['response_time'] is not None:
            response_times.append(item['response_time'])
            tokens = item['input_tokens'] + item['output_tokens_before_timeout']
            total_tokens.append(tokens)
            throughputs.append(1000*tokens / item['response_time'])
else:
    print("Unexpected data format")

avg_throughput = np.mean(throughputs)

plt.scatter(total_tokens, response_times, c=throughputs, cmap='viridis')
plt.colorbar(label='Throughput (tokens/sec)')
plt.title('Response Time as a Function of Total Tokens')
plt.xlabel('Total Tokens (Input + Output Before Timeout)')
plt.ylabel('Response Time (ms)')
plt.axhline(y=avg_throughput, color='r', linestyle='--')
plt.text(max(total_tokens) * 0.5, avg_throughput + 100, f'Avg Throughput: {avg_throughput:.2f} tokens/sec', color='r')

plt.savefig('output/response_times_vs_tokens.png')
