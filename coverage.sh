#!/bin/bash

# Find all .gcda files and run gcov on them with the output as the current directory
echo "Running gcov on all .gcda files..."
find . -name "*.gcda" -exec gcov -p -o {} ./ \;


# Run remote codecov script to upload - gcov is disabled as we already have the reports
echo "Uploading coverage data..."
bash <(curl -s https://codecov.io/bash) -X gcov