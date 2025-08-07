import csv

def load_data(file_path):

    with open(file_path, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        data = [row for row in reader]
    return data
def save_result_to_csv(result, output_path):
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Result'])
        writer.writerow([result])