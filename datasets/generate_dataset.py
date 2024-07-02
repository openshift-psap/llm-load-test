import json  
import random  
import string  
import argparse  
import wonderwords
import tiktoken

def num_tokens_from_string(input_string) -> int:
        """Returns the number of tokens in a text string."""
        encoding = tiktoken.get_encoding("cl100k_base")
        num_tokens = len(encoding.encode(input_string))
        return num_tokens


def generate_random_words(length):  
    """Generate a string of random words of a given length.""" 
    r = wonderwords.RandomWord() 
    words=[]
    remaining_tokens= length

    while True:
        remaining_words = ((remaining_tokens // 4) + 1)
        words.extend(r.random_words(amount= remaining_words))
        token_count = num_tokens_from_string(" ".join(words))
        remaining_tokens = length - token_count
        if remaining_tokens <= 0:
            break
    return ' '.join(words)  
  
def generate_dataset(tok_input_length, tok_output_length, N):  
    dataset = []  
    for seq_id in range(N):  
        user_query = f"write a long essay about life in at least {tok_output_length} tokens."
        entry = {  
            "index": seq_id,  
            "system_prompt": generate_random_words(tok_input_length - num_tokens_from_string(user_query)),  
            "question": user_query,  
            "expected_output": "NA",  
            "tok_input_length": tok_input_length,  
            "tok_output_length": tok_output_length  
        }  
        dataset.append(entry)  
    return dataset  
  
def save_to_jsonl(dataset, filename):  
    with open(filename, 'w') as f:  
        for entry in dataset:  
            f.write(json.dumps(entry) + '\n')  
  
def main():  
    parser = argparse.ArgumentParser(description="Generate a random text dataset in JSON Lines format.")  
    parser.add_argument('--tok_input_length', type=int, required=True, help="Token input length")  
    parser.add_argument('--tok_output_length', type=int, required=True, help="Token output length")  
    parser.add_argument('--N', type=int, required=True, help="Number of samples")  
    parser.add_argument('--output_file', type=str, default='random_text_dataset.jsonl', help="Output file name")  
  
    args = parser.parse_args()  
  
    # Generate dataset  
    dataset = generate_dataset(args.tok_input_length, args.tok_output_length, args.N)  
  
    # Save dataset to jsonl file  
    save_to_jsonl(dataset, args.output_file)  
  
if __name__ == "__main__":  
    main()  
