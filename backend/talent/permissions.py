from rest_framework.permissions import BasePermission




class IsRecruiter(BasePermission):
    def has_permission(self, request, view):
        return hasattr(request.user, "recruiter_profile")





class IsCandidate(BasePermission):
    def has_permission(self, request, view):
        return hasattr(request.user, "candidate_profile")




