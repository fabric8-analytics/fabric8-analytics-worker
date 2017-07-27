Directory for not-yet-upstream-released patches.

Sometimes you might need to apply a patch that has not been released upstream yet.
The following instructions describe patching of f8a_worker/'s dependencies.

To create and apply the patch:
* go into cloned upstream repository with patch applied (for example in your not yet upstream merged branch)
* create patch with `git format-patch <hash>^..<hash>`
* copy it into hack/patches/
* modify hack/patches/apply_patches.sh to apply the patch during image build
