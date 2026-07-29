// MongoDB initialization script
// Runs once on container first start
db = db.getSiblingDB('recruitzaa');

// Create collections with validators
db.createCollection('candidate_profiles', {
    validator: {
        $jsonSchema: {
            bsonType: 'object',
            required: ['user_id', 'created_at'],
            properties: {
                user_id: { bsonType: 'string' },
                created_at: { bsonType: 'date' }
            }
        }
    }
});

db.createCollection('ai_results');
db.createCollection('jobs');
db.createCollection('applications');
db.createCollection('kanban_boards');
db.createCollection('employer_profiles');
db.createCollection('expert_cards');
db.createCollection('chat_sessions');
db.createCollection('scraped_jobs');

// Indexes for candidate_profiles
db.candidate_profiles.createIndex({ user_id: 1 }, { unique: true });

// Indexes for ai_results
db.ai_results.createIndex({ user_id: 1 });
db.ai_results.createIndex({ job_id: 1 });
db.ai_results.createIndex({ user_id: 1, job_id: 1 }, { unique: true });

// Indexes for jobs
db.jobs.createIndex({ status: 1 });
db.jobs.createIndex({ employer_id: 1 });
db.jobs.createIndex({ title: 'text', description: 'text' });

// Indexes for applications
db.applications.createIndex({ candidate_id: 1 });
db.applications.createIndex({ job_id: 1 });
db.applications.createIndex({ candidate_id: 1, job_id: 1 }, { unique: true });

// Indexes for kanban_boards
db.kanban_boards.createIndex({ candidate_id: 1 }, { unique: true });

// Indexes for expert_cards
db.expert_cards.createIndex({ user_id: 1 }, { unique: true });
db.expert_cards.createIndex({ specializations: 1 });
db.expert_cards.createIndex({ is_available: 1 });

// Indexes for chat_sessions
db.chat_sessions.createIndex({ user_id: 1 });
db.chat_sessions.createIndex({ created_at: -1 });

print('✅ Recruitzaa MongoDB initialized');
