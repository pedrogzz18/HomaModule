TMP_DIR=$(mktemp -d)
bazel-bin/analysis/results_conversion --input_file=$1 --output_directory=${TMP_DIR} --supress_header

cp ${TMP_DIR}/overall_summary.txt $3/$2-0.rtts
