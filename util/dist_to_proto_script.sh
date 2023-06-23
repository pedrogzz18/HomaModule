#!/bin/bash
# This script creates new text proto files from the modified workload
# distributions in the HomaModule/util/dist.cc
# Usage: ./dist_to_proto_script workload [max message length]
# [min bucket frac] [max size ratio] [Gbps] [node count] [test duration]
# Gbps determines the value of open_loop_interval_ns and is computed in
# dist_to_proto.cc. Test duration is in seconds.

function proto()
{
cat << EOF
tests {
  attributes: { key: 'workload' value: '${1}' }
  attributes: { key: 'max_message_length' value: '${2}' }
  attributes: { key: 'min_bucket_frac' value: '${3}' }
  attributes: { key: 'max_size_ratio' value: '${4}' }
  attributes: { key: 'Gbps' value: '${5}' }
  attributes: { key: 'num_nodes' value: '${6}' }
  attributes: { key: 'test_duration_s' value: '${7}' }
  protocol_driver_options {
    name: 'default_protocol_driver_options'
    protocol_name: 'homa'
  }
  name: 'homa_test'
  services {
    name: 'clique'
    count: ${6}
  }
  action_lists {
    name: 'clique'
    action_names: 'clique_queries'
  }
  actions {
    name: 'clique_queries'
    iterations {
      max_duration_us: ${7}000000
      open_loop_interval_ns: $interval
      open_loop_interval_distribution: 'exponential_distribution'
      warmup_iterations: 1500
    }
    rpc_name: 'clique_query'
  }
  rpc_descriptions {
    name: 'clique_query'
    client: 'clique'
    server: 'clique'
    fanout_filter: 'random'
    distribution_config_name: "dist_config"
  }
  action_lists {
    name: 'clique_query'
    # no actions, NOP
  }
  overload_limits {
    max_pending_rpcs: 5000
  }
  distribution_config {
    name: "dist_config"
    field_names: "payload_size"
$body
  }
}
EOF
}

interval_file=$(mktemp)
body=$(dist_to_proto "${@}" 2> $interval_file)
interval=$(cat $interval_file)
proto "${@}"
rm ${interval_file}
