pipeline {
    agent any

    environment {
        PYTHONUNBUFFERED = '1'
        DJANGO_SETTINGS_MODULE = 'config.settings.test' // Adjust if your test settings path differs
        SECRET_KEY = 'ci-dummy-secret-key-for-testing'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Set Up Environment') {
            steps {
                sh '''
                    python -m venv venv
                    . venv/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements.txt
                '''
            }
        }

        stage('Run Tests') {
            steps {
                sh '''
                    . venv/bin/activate
                    python backend/manage.py test
                '''
            }
        }
    }

    post {
        always {
            cleanWs()
        }
    }
}