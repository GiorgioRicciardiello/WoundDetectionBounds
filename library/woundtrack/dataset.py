"""
woundtrack.dataset
==================

ML-ready dataset interface for wound segmentation training.

CRITICAL DESIGN RULES:
- This module must NOT import qc, edges, or metrics
- Dataset uses only raw images and masks
- No derived quantities or wound geometry assumptions
- Ready for PyTorch or TensorFlow integration
"""

from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np

from .types import TrajectoriesDict, TimeT
from .utils import ensure_binary_mask

__all__ = [
    "WoundSegmentationDataset",
]


class WoundSegmentationDataset:
    """
    Dataset yielding (image, mask) pairs for wound segmentation training.
    
    This class provides a clean abstraction for training segmentation models
    on wound-healing microscopy data. It extracts image-mask pairs at a
    specified timepoint and applies optional transforms.
    
    Parameters
    ----------
    trajectories : Dict[str, Dict]
        Raw trajectories dictionary where each key maps to a trajectory dict
        containing 'results' list with timepoint entries.
    time : int or float, default=0
        Which timepoint to extract (default: t=0 baseline).
    transform : Callable, optional
        Transform to apply to images. Should accept np.ndarray and return
        np.ndarray (or tensor for PyTorch).
    target_transform : Callable, optional
        Transform to apply to masks. Should accept np.ndarray and return
        np.ndarray (or tensor for PyTorch).
    return_key : bool, default=False
        If True, __getitem__ returns (image, mask, trajectory_key).
    expand_dims : bool, default=False
        If True, expand image/mask from (H, W) to (1, H, W) for channel dim.
    
    Attributes
    ----------
    samples : List[Tuple[str, Dict]]
        Internal index of (trajectory_key, result_dict) pairs.
    
    Examples
    --------
    # Basic usage
    dataset = WoundSegmentationDataset(trajectories, time=0)
    img, mask = dataset[0]
    print(img.shape, mask.shape)
    
    # With transforms for PyTorch
    import torch
    def to_tensor(x):
         return torch.from_numpy(x).float()
    dataset = WoundSegmentationDataset(
         trajectories,
         transform=to_tensor,
         target_transform=to_tensor,
         expand_dims=True,
     )
    
    # With DataLoader
    from torch.utils.data import DataLoader
    loader = DataLoader(dataset, batch_size=8, shuffle=True)
    """
    
    def __init__(
        self,
        trajectories: TrajectoriesDict,
        time: TimeT = 0,
        transform: Optional[Callable[[np.ndarray], Any]] = None,
        target_transform: Optional[Callable[[np.ndarray], Any]] = None,
        return_key: bool = False,
        expand_dims: bool = False,
    ) -> None:
        self.time = time
        self.transform = transform
        self.target_transform = target_transform
        self.return_key = return_key
        self.expand_dims = expand_dims
        
        # Build internal index
        self.samples: List[Tuple[str, Dict[str, Any]]] = []
        self._build_index(trajectories)
    
    def _build_index(self, trajectories: TrajectoriesDict) -> None:
        """
        Build internal index of valid (trajectory_key, result_dict) pairs.
        
        Skips trajectories that are missing:
        - The requested timepoint
        - img_raw field
        - mask field
        """
        for traj_key, traj_data in trajectories.items():
            results = traj_data.get("results", [])
            
            # Find result matching requested time
            result = None
            for r in results:
                if r.get("t") == self.time:
                    result = r
                    break
            
            if result is None:
                continue
            
            # Validate required fields
            img = result.get("img_raw")
            mask = result.get("mask")
            
            if img is None or mask is None:
                continue
            
            # Add to index
            self.samples.append((traj_key, result))
    
    def __len__(self) -> int:
        """Return number of valid (image, mask) pairs."""
        return len(self.samples)
    
    def __getitem__(
        self, idx: int
    ) -> Union[Tuple[np.ndarray, np.ndarray], Tuple[np.ndarray, np.ndarray, str]]:
        """
        Get (image, mask) pair at index.
        
        Parameters
        ----------
        idx : int
            Index into the dataset.
        
        Returns
        -------
        image : np.ndarray
            Grayscale image, shape (H, W) or (1, H, W) if expand_dims=True.
        mask : np.ndarray
            Binary mask, shape (H, W) or (1, H, W) if expand_dims=True.
        trajectory_key : str, optional
            Only returned if return_key=True.
        
        Raises
        ------
        IndexError
            If idx is out of range.
        """
        if idx < 0 or idx >= len(self.samples):
            raise IndexError(f"Index {idx} out of range for dataset of size {len(self.samples)}")
        
        traj_key, result = self.samples[idx]
        
        # Extract image and mask
        image = np.asarray(result["img_raw"])
        mask = np.asarray(result["mask"])
        
        # Ensure mask is binary
        mask = ensure_binary_mask(mask)
        
        # Expand dimensions if requested (H, W) -> (1, H, W)
        if self.expand_dims:
            image = image[np.newaxis, ]
            mask = mask[np.newaxis, ]
        
        # Apply transforms
        if self.transform is not None:
            image = self.transform(image)
        
        if self.target_transform is not None:
            mask = self.target_transform(mask)
        
        if self.return_key:
            return image, mask, traj_key
        
        return image, mask
    
    def get_trajectory_key(self, idx: int) -> str:
        """
        Get trajectory key for a given index.
        
        Parameters
        ----------
        idx : int
            Index into the dataset.
        
        Returns
        -------
        str
            Trajectory key.
        """
        if idx < 0 or idx >= len(self.samples):
            raise IndexError(f"Index {idx} out of range")
        return self.samples[idx][0]
    
    def get_all_keys(self) -> List[str]:
        """
        Get all trajectory keys in the dataset.
        
        Returns
        -------
        List[str]
            List of trajectory keys in dataset order.
        """
        return [key for key, _ in self.samples]
    
    @property
    def image_shape(self) -> Optional[Tuple[int, ]]:
        """
        Get shape of images in dataset.
        
        Returns None if dataset is empty.
        """
        if len(self.samples) == 0:
            return None
        
        _, result = self.samples[0]
        shape = np.asarray(result["img_raw"]).shape
        
        if self.expand_dims:
            return (1,) + shape
        return shape
