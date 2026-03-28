#!/usr/bin/env nextflow
nextflow.enable.dsl=2

process smoke {
  output:
    path "smoke.txt"

  script:
  """
  echo "smoke-ok" > smoke.txt
  """
}

workflow {
  smoke()
}
