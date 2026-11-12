pipeline {
    agent any

    environment {
        REGISTRY = "docker.io" // Change to your registry if using AWS ECR or GitHub Packages
        IMAGE_NAME = "wasimakramshaik/fhbp-backend"
        DOCKER_CREDS = credentials('dockerhub-credentials') // Jenkins credential ID
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

        stage('Build and Push Docker Image') {
            steps {
                script {
                    // Log in to Docker registry using Jenkins credentials
                    sh 'echo $DOCKER_CREDS_PSW | docker login $REGISTRY -u $DOCKER_CREDS_USR --password-stdin'
                    
                    // Build image using your infrastructure Dockerfile path
                    app = docker.build("${IMAGE_NAME}:${env.BUILD_NUMBER}", "-f infrastructure/docker/Dockerfile.backend .")
                    
                    // Push latest and build-number tags
                    app.push("${env.BUILD_NUMBER}")
                    app.push("latest")
                }
            }
        }
    }

    post {
        always {
            cleanWs()
        }
    }
}