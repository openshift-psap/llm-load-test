import requests
from requests.auth import HTTPBasicAuth
import yaml
import json
import time
import pandas as pd

import urllib3
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# Suppress only the single InsecureRequestWarning from urllib3
urllib3.disable_warnings(InsecureRequestWarning)

class PrometheusClient:
    def __init__(self, base_url, user, password):
        """
        Initialize the Prometheus client with the base URL and authentication credentials.
        
        :param base_url: Base URL of the Prometheus server.
        :param user: Username for basic authentication.
        :param password: Password for basic authentication.
        """
        self.base_url = base_url
        self.auth = HTTPBasicAuth(user, password)

    def get_nearest_metric(self, query, timestamp, expected_labels, range_seconds=10):
        """
        Get the metric value nearest to the specified timestamp from Prometheus and match the expected labels.

        :param query: Prometheus query.
        :param timestamp: Timestamp to find the nearest value (in Unix time with fractional seconds).
        :param expected_labels: Dictionary of expected labels to filter the metric.
        :param range_seconds: Range in seconds to search around the timestamp.
        :return: Filtered metric value from Prometheus.
        """
        # Try to get the exact timestamp first
        params = {
            'query': query,
            'time': timestamp
        }

        response = requests.get(f'{self.base_url}/api/v1/query', params=params, auth=self.auth, verify=False)

        if response.status_code == 200:
            data = response.json().get('data', {}).get('result', [])
            for result in data:
                if all(item in result['metric'].items() for item in expected_labels.items()):
                    return result

        # If exact match not found, perform a range query
        start_time = timestamp - range_seconds
        end_time = timestamp + range_seconds
        params = {
            'query': query,
            'start': start_time,
            'end': end_time,
            'step': '1s'  # 1-second step to get fine-grained data
        }

        response = requests.get(f'{self.base_url}/api/v1/query_range', params=params, auth=self.auth, verify=False)

        if response.status_code == 200:
            data = response.json().get('data', {}).get('result', [])
            if data:
                # Find the data point closest to the timestamp
                closest_point = None
                closest_time_diff = float('inf')
                for result in data:
                    for value in result['values']:
                        time_diff = abs(value[0] - timestamp)
                        if time_diff < closest_time_diff:
                            if all(item in result['metric'].items() for item in expected_labels.items()):
                                closest_point = {
                                    'metric': result['metric'],
                                    'value': value[1],
                                    'timestamp': value[0]
                                }
                                closest_time_diff = time_diff
                return closest_point
        else:
            response.raise_for_status()

        return None

def load_config(config_file):
    """
    Load configuration from a YAML file.

    :param config_file: Path to the YAML configuration file.
    :return: Configuration data.
    """
    with open(config_file, 'r') as file:
        config = yaml.safe_load(file)
    return config

def load_json(json_file):
    """
    Load JSON data from a file.

    :param json_file: Path to the JSON file.
    :return: JSON data.
    """
    with open(json_file, 'r') as file:
        data = json.load(file)
    return data

def save_json(data, json_file):
    """
    Save JSON data to a file.

    :param data: JSON data to save.
    :param json_file: Path to the JSON file.
    """
    with open(json_file, 'w') as file:
        json.dump(data, file, indent=4)

def get_summary(df: pd.DataFrame, output_obj: dict, summary_key: str):
    """Get the summary."""
    output_obj["summary"][summary_key] = {}
    output_obj["summary"][summary_key]["min"] = df[summary_key].min()
    output_obj["summary"][summary_key]["max"] = df[summary_key].max()
    output_obj["summary"][summary_key]["median"] = df[summary_key].median()
    output_obj["summary"][summary_key]["mean"] = df[summary_key].mean()
    output_obj["summary"][summary_key]["percentile_80"] = df[summary_key].quantile(0.80)
    output_obj["summary"][summary_key]["percentile_90"] = df[summary_key].quantile(0.90)
    output_obj["summary"][summary_key]["percentile_95"] = df[summary_key].quantile(0.95)
    output_obj["summary"][summary_key]["percentile_99"] = df[summary_key].quantile(0.99)
    return output_obj

# Usage example
if __name__ == "__main__":
    # Load configuration from config.yaml
    config_file = '../config.yaml'  # Adjust the path to your config file
    config = load_config(config_file)

    # Load JSON data from output1.json
    json_file = '../output/output1.json'  # Adjust the path to your JSON file
    json_data = load_json(json_file)

    # Check if metadata_extensions_enabled is True and metadata_extensions_options exists
    if config.get('metadata_extensions_enabled', False) and 'metadata_extensions_options' in config:
        metrics_data = []

        for prometheus_options in config['metadata_extensions_options']:
            metadata_plugin_name = next(iter(prometheus_options))
            for prometheus_config in prometheus_options.get(metadata_plugin_name, []):
                base_url = prometheus_config['base_url']
                user = prometheus_config['user']
                password = prometheus_config['password']
                metric = prometheus_config['metric']
                expected_labels = prometheus_config['expected_labels']
                # Initialize the Prometheus client
                client = PrometheusClient(base_url, user, password)

                # Loop over each result in the JSON data
                for result in json_data['results']:
                    timestamp = result['start_time']

                    # Get the nearest metric value with expected labels
                    try:
                        metric_data = client.get_nearest_metric(metric, timestamp, expected_labels)
                        print(metric_data)
                        if metric_data:
                            if 'metadata' not in result:
                                result['metadata'] = []
                            
                            metadata_obj = {
                                'metadata_plugin_name': metadata_plugin_name,
                                'key': metric,
                                'timestamp': metric_data['value'][0],
                                'value': float(metric_data['value'][1]),
                                'labels': expected_labels
                            }
                            result['metadata'].append(metadata_obj)
                            metrics_data.append(metadata_obj)
                        else:
                            print(f"Metric '{metric}' with the specified labels not found for timestamp {timestamp}.")
                    except requests.exceptions.RequestException as e:
                        print(f"Error fetching metrics for timestamp {timestamp}: {e}")

        # Convert metrics data to DataFrame and summarize
        if metrics_data:
            metrics_df = pd.DataFrame(metrics_data)
            if 'summary' not in json_data:
                json_data['summary'] = {}

            for metric_key in metrics_df['key'].unique():

                #print(' ')
                #print(' ')
                #print('metric key')
                #print(metric_key)
                metric_df = metrics_df[metrics_df['key'] == metric_key]
                #print(metric_df)
                # Prepare a temporary dictionary to hold summary information
                temp_summary = {}
                # Get the summary for all the values in the 'value' column
                temp_summary = get_summary(metric_df, json_data, 'value')
                # Update the main JSON data summary with the new summary information
                #print('---')
                #print('---')
                #print(temp_summary)
                #print('---')
                #print('---')
                #print('---')
                #print(temp_summary)
                json_data['summary'][metric_key] = temp_summary['summary']['value']

        # Check the loop condition FIXME
        if 'value' in json_data['summary']:
            del json_data['summary']['value']

        # Save the updated JSON data back to the file
        save_json(json_data, json_file)
    else:
        print("Metadata extensions are not enabled or the configuration is missing.")
