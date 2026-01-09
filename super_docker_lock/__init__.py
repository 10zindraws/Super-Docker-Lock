from .super_docker_lock import SuperDockerLockExtension

from krita import Krita, Extension

inst = Krita.instance()
inst.addExtension(SuperDockerLockExtension(inst)) 


