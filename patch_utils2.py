import re

with open('vdx_project/vdx/utils.py', 'r') as f:
    utils_content = f.read()

utils_top = utils_content.split('def process_mdl_and_extract')[0]

with open('test_structure.py', 'r') as f:
    test_content = f.read()

# Extract from def process_mdl_and_extract down to before if __name__
test_func = test_content.split('def process_mdl_and_extract')[1].split('if __name__ == "__main__":')[0]

with open('vdx_project/vdx/utils.py', 'w') as f:
    f.write(utils_top + 'def process_mdl_and_extract' + test_func)

