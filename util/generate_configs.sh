#1/bin/bash
# This script generates all 5 protofiles from the workload distributions in
# HomaModule/util/dist.cc into the folder named homa_experiments with files
# titled homa_test_w(1-5).config by calling dist_to_proto_script.sh in
# HomaModule/util.
# dist_to_proto_script.sh is called with arguments: workload [max message length]
# [min bucket frac] [max size ratio] [Gbps] [node count] [test duration]
# Gbps value is a determined by which value gives a result of at least >= 100 ms
# for open_loop_interval_ns with a min of 1 Gbps and a max of 20 Gbps. The default
# test duration is 10 seconds, max message length is from cp_node and arguments
# 3 and 4 are from dist.h. Test duration is in seconds.

MYPATH=$(dirname $(readlink -sf $(which $0)))
PATH=$PATH:$MYPATH

mkdir -p homa_experiments
cd homa_experiments
dist_to_proto_script.sh w1 1000000 0.0025 1.2 1 \
  10 10 > homa_test_w1.config
dist_to_proto_script.sh w2 1000000 0.0025 1.2 1 \
  10 10 > homa_test_w2.config
dist_to_proto_script.sh w3 1000000 0.0025 1.2 2 \
  10 10 > homa_test_w3.config
dist_to_proto_script.sh w4 1000000 0.0025 1.2 20 \
  10 10 > homa_test_w4.config
dist_to_proto_script.sh w5 1000000 0.0025 1.2 20 \
  10 10 > homa_test_w5.config
