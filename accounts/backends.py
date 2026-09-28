"""Authentication backend that also matches mailhashed accounts.

A converted (mailhashed) account no longer stores the plain email, so the
default ModelBackend cannot find it by address. This backend first tries the
normal username/password path, then - if that fails - looks the user up by
sha256 of the lowercased identifier and checks the password against that
user. Nothing about the response differs between the paths, so hashed
accounts neither lose email login nor become distinguishable.
"""

import hashlib

from django.contrib.auth.backends import ModelBackend

from accounts.models import UserProfile


class HashedEmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        user = super().authenticate(request, username=username, password=password, **kwargs)
        if user is None and username and password:
            digest = hashlib.sha256(username.strip().lower().encode()).hexdigest()
            profile = (
                UserProfile.objects.filter(mailhashed=True, email_hash=digest)
                .select_related("user")
                .first()
            )
            if profile is not None and profile.user.check_password(password):
                if self.user_can_authenticate(profile.user):
                    return profile.user
        return user
