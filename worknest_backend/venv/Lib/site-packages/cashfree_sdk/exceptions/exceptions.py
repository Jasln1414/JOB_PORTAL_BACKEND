
class IncompleteParametersError(Exception):
    pass

class CredsNotPresentError(Exception):
    pass

class AuthenticationFailureError(Exception):
    pass

class ServiceDownError(Exception):
    pass

class IncorrectCredsError(Exception):
    pass

class TokenGenFailedError(Exception):
    pass

class ModuleNotInitiatedError(Exception):
    pass

class InternalServerError(Exception):
    pass

class BadRequestError(Exception):
    pass

class ForbiddenError(Exception):
    pass

class EntityDoesntExistError(Exception):
    pass

class MethodNotAllowedError(Exception):
    pass

class AlreadyExistError(Exception):
    pass

class PreconditionFailedError(Exception):
    pass

class RequestTooLargeError(Exception):
    pass

class InputWrongFormatError(Exception):
    pass

class TooManyRequestError(Exception):
    pass

class UnknownErrorOccurredError(Exception):
    pass

class ConfigMissingForSignatureAuth(Exception):
    pass

class InvalidPublicKeyError(Exception):
    pass

class SignatureCreationFailedError(Exception):
    pass

class InvalidaWebHookPayloadTypeError(Exception):
    pass

class RequestFailedError(Exception):
    pass