# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

run "setup_tests" {
  module {
    source = "./tests/setup"
  }
}

run "basic_deploy" {
  variables {
    model_uuid = run.setup_tests.model_uuid
    channel    = "latest/edge"
    # renovate: depName="mariadb-k8s"
    revision = 1
  }

  assert {
    condition     = output.app_name == "mariadb-k8s"
    error_message = "mariadb-k8s app_name did not match expected"
  }
}

run "integration_test" {
  variables {
    model_uuid = run.setup_tests.model_uuid
  }

  module {
    source = "./tests/integration_test"
  }

  assert {
    condition     = data.external.app_status.result.status == "active"
    error_message = "mariadb-k8s did not reach active status"
  }
}
