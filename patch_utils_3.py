with open('test_reassemble.py', 'r') as f:
    content = f.read()

func_code = content.split('# Generate some dummy data to test')[0].replace('import os\nimport re\n\n', '')

with open('vdx_project/vdx/utils.py', 'a') as f:
    f.write('\n' + func_code)
