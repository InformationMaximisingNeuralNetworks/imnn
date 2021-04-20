pipeline {
  agent any
  stages {
    stage('Set up environment') {
      steps {
        sh '''python3 -m venv py_imnn
source py_imnn/bin/activate
pip install --upgrade pip
pip install pytest flake8
pip install -e .'''
      }
    }

    stage('Flake') {
      steps {
        sh '''source py_imnn/bin/activate
flake8 . --extend-exclude=dist,build,docs,examples,IMNN.egg-info,__pycache__,py_imnn,imnn/utils/jac.py,.ipynb_checkpoints --ignore=E741,W503,W504,F403,F405 --show-source --statistics
      }
    }

    stage('Testing _IMNN') {
      parallel {
        stage('Testing _IMNN') {
          steps {
            sh '''source py_imnn/bin/activate
python -m pytest --junitxml=junitxml IMNN/experimental/jax/imnn/_imnn_test.py'''
          }
        }

        stage('Testing SimulatorIMNN') {
          steps {
            sh '''source py_imnn/bin/activate
python -m pytest --junitxml=junitxml IMNN/experimental/jax/imnn/simulator_imnn_test.py'''
          }
        }

        stage('Testing AggregatedSimulatorIMNN') {
          steps {
            sh '''source py_imnn/bin/activate
python -m pytest --junitxml=junitxml IMNN/experimental/jax/imnn/aggregated_simulator_imnn_test.py'''
          }
        }

        stage('Testing GradientIMNN') {
          steps {
            sh '''source py_imnn/bin/activate
python -m pytest --junitxml=junitxml IMNN/experimental/jax/imnn/gradient_imnn_test.py'''
          }
        }

        stage('Testing AggregatedGradientIMNN') {
          steps {
            sh '''source py_imnn/bin/activate
python -m pytest --junitxml=junitxml IMNN/experimental/jax/imnn/aggregated_gradient_imnn_test.py'''
          }
        }

        stage('Testing NumericalGradientIMNN') {
          steps {
            sh '''source py_imnn/bin/activate
python -m pytest --junitxml=junitxml IMNN/experimental/jax/imnn/numerical_gradient_imnn_test.py'''
          }
        }

        stage('Testing AggregatedNumericalGradientIMNN') {
          steps {
            sh '''source py_imnn/bin/activate
python -m pytest --junitxml=junitxml IMNN/experimental/jax/imnn/aggregated_numerical_gradient_imnn_test.py'''
          }
        }

      }
    }

  }
}
