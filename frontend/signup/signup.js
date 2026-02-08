document.getElementById('signupForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const name = document.getElementById('name').value;
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    
    // Basic client-side validation
    if (password.length < 8) {
        alert('Password must be at least 8 characters long');
        return;
    }
    
    if (!/[A-Z]/.test(password)) {
        alert('Password must contain at least one uppercase letter');
        return;
    }
    
    if (!/[a-z]/.test(password)) {
        alert('Password must contain at least one lowercase letter');
        return;
    }
    
    if (!/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
        alert('Password must contain at least one special character');
        return;
    }
    
    try {
        const response = await fetch('/api/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                name: name,
                email: email.toLowerCase(),
                password: password
            })
        });
        
        if (response.ok) {
            alert('Account created successfully! Please log in.');
            window.location.href = '/login';
        } else {
            const errorData = await response.json();
            alert(errorData.detail || 'Registration failed');
        }
    } catch (error) {
        console.error('Registration error:', error);
        alert('An error occurred during registration');
    }
});