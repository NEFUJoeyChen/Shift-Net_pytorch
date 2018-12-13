import random
import math
import numpy as np
import torch
import torch.nn as nn
from time import time

class Modified_NonparametricShift(object):

    def _extract_patches_from_flag(self, img, patch_size, stride, flag, value):
        input_windows = self._unfold(img, patch_size, stride)

        input_windows = self._filter(input_windows, flag, value)

        return self._norm(input_windows)

    def _paste(self, img, patch_size, stride, transition_matrix):
        #t0 = time()
        input_windows, i_2, i_3, i_1, i_4 = self._unfold(img, patch_size, stride, with_indexes=True)
        
        #t1 = time()
        #print('_unfold', t1 - t0)

        #print(input_windows.shape)
        #print(transition_matrix.shape)
        #t0 = time()
        ## PASTE NEW FEATURES
        input_windows = torch.mm(transition_matrix, input_windows) #patch * input_windows#[flag == 1] = patch
        #t1 = time()
        #print('PASTE', t1 - t0)

        ## RESIZE TO CORRET CONV FEATURES FORMAT
        input_windows = input_windows.view(i_2, i_3, i_1, i_4)
        input_windows = input_windows.permute(3, 2, 0, 1)
        return input_windows

    def _unfold(self,  img, patch_size, stride, with_indexes=False):
        n_dim = 3
        assert img.dim() == n_dim, 'image must be of dimension 3.'

        kH, kW = patch_size, patch_size
        dH, dW = stride, stride
        input_windows = img.unfold(1, kH, dH).unfold(2, kW, dW)

        i_1, i_2, i_3, i_4, i_5 = input_windows.size(0), input_windows.size(1), input_windows.size(
            2), input_windows.size(3), input_windows.size(4)

        if with_indexes:
            input_windows = input_windows.permute(1, 2, 0, 3, 4).contiguous().view(i_2 * i_3, i_1)
            return input_windows, i_2, i_3, i_1, i_4
        else:
            input_windows = input_windows.permute(1, 2, 0, 3, 4).contiguous().view(i_2 * i_3, i_1, i_4, i_5)
            return input_windows

    def _filter(self, input_windows, flag, value):
        ## EXTRACT MASK OR NOT DEPENDING ON VALUE
        input_window = input_windows[flag == value]
        return input_window.view(input_window.size(0), -1)


    def _norm(self, input_window):
        # This norm is incorrect.
        #return torch.norm(input_window, dim=1, keepdim=True)
        for i in range(input_window.size(0)):
           input_window[i] = input_window[i]*(1/(input_window[i].norm(2)+1e-8))

        return input_window

class NonparametricShift(object):
    def buildAutoencoder(self, target_img, normalize, interpolate,  nonmask_point_idx, patch_size=1, stride=1):
        nDim = 3
        assert target_img.dim() == nDim, 'target image must be of dimension 3.'
        C = target_img.size(0)

        self.Tensor = torch.cuda.FloatTensor if torch.cuda.is_available else torch.Tensor

        patches_all, patches_part = self._extract_patches(target_img, patch_size, stride, nonmask_point_idx)
        npatches_part = patches_part.size(0)
        npatches_all = patches_all.size(0)


        conv_enc_non_mask, conv_dec_non_mask = self._build(patch_size, stride, C, patches_part, npatches_part, normalize, interpolate)
        conv_enc_all, conv_dec_all = self._build(patch_size, stride, C, patches_all, npatches_all, normalize, interpolate)

        return conv_enc_all, conv_enc_non_mask, conv_dec_all, conv_dec_non_mask

    def _build(self, patch_size, stride, C, target_patches, npatches, normalize, interpolate):
        # for each patch, divide by its L2 norm.
        enc_patches = target_patches.clone()
        for i in range(npatches):
            enc_patches[i] = enc_patches[i]*(1/(enc_patches[i].norm(2)+1e-8))
        conv_enc = nn.Conv2d(C, npatches, kernel_size=patch_size, stride=stride, bias=False)
        conv_enc.weight.data = enc_patches

        # normalize is not needed, it doesn't change the result!
        if normalize:
            raise NotImplementedError

        if interpolate:
            raise NotImplementedError

        conv_dec = nn.ConvTranspose2d(npatches, C, kernel_size=patch_size, stride=stride, bias=False)
        conv_dec.weight.data = target_patches

        return conv_enc, conv_dec

    def _extract_patches(self, img, patch_size, stride, nonmask_point_idx):
        n_dim = 3
        assert img.dim() == n_dim, 'image must be of dimension 3.'

        kH, kW = patch_size, patch_size
        dH, dW = stride, stride
        input_windows = img.unfold(1, kH, dH).unfold(2, kW, dW)
        
        i_1, i_2, i_3, i_4, i_5 = input_windows.size(0), input_windows.size(1), input_windows.size(2), input_windows.size(3), input_windows.size(4)
        input_windows = input_windows.permute(1,2,0,3,4).contiguous().view(i_2*i_3, i_1, i_4, i_5)
        
        patches_all = input_windows
        patches = input_windows.index_select(0, nonmask_point_idx) #It returns a new tensor, representing patches extracted from non-masked region!
        return patches_all, patches

