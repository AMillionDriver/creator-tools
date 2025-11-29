const http = require('http');

const options = {
    hostname: '127.0.0.1',
    port: 5000,
    path: '/',
    method: 'GET'
};

const req = http.request(options, res => {
    // Any response from the server means it's running
    console.log('\x1b[32m%s\x1b[0m', '✅ Backend is running!'); // Green text
    console.log(`   You can access the application at: http://127.0.0.1:5000`);
});

req.on('error', error => {
    if (error.code === 'ECONNREFUSED') {
        console.error('\x1b[31m%s\x1b[0m', '❌ Backend is not running.'); // Red text
        console.error('   Please run "npm run dev:backend" in another terminal to start the server.');
    } else {
        console.error('\x1b[31m%s\x1b[0m', 'An unexpected error occurred:'); // Red text
        console.error(error);
    }
});

req.end();
