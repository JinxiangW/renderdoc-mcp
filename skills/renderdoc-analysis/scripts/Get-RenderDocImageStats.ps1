param(
    [string]$OverlayPath,
    [string]$PreviousPath,
    [string]$CurrentPath,
    [int]$OverlayThreshold = 24,
    [int]$DiffThreshold = 4
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Drawing

if (-not ([System.Management.Automation.PSTypeName]'RenderDocImageStats').Type) {
$drawingAssembly = [System.Drawing.Bitmap].Assembly.Location
Add-Type -ReferencedAssemblies @($drawingAssembly) @"
using System;
using System.Drawing;
using System.Drawing.Imaging;

public struct PixelBox
{
    public bool hasBox;
    public int minX;
    public int minY;
    public int maxX;
    public int maxY;
}

public class OverlayStats
{
    public int width;
    public int height;
    public long activePixels;
    public double coverage;
    public PixelBox bounds;
}

public class DiffStats
{
    public int width;
    public int height;
    public long changedPixels;
    public double changeRatio;
    public double meanDiff;
    public PixelBox bounds;
}

public static class RenderDocImageStats
{
    private static Bitmap Normalize(Bitmap src)
    {
        Bitmap clone = new Bitmap(src.Width, src.Height, PixelFormat.Format32bppArgb);
        using(Graphics g = Graphics.FromImage(clone))
        {
            g.DrawImage(src, new Rectangle(0, 0, clone.Width, clone.Height));
        }
        return clone;
    }

    public static OverlayStats ComputeOverlay(string path, int threshold)
    {
        using(Bitmap loaded = (Bitmap)Image.FromFile(path))
        using(Bitmap bmp = Normalize(loaded))
        {
            Rectangle rect = new Rectangle(0, 0, bmp.Width, bmp.Height);
            BitmapData data = bmp.LockBits(rect, ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);

            try
            {
                int stride = data.Stride;
                int bytes = stride * bmp.Height;
                byte[] raw = new byte[bytes];
                System.Runtime.InteropServices.Marshal.Copy(data.Scan0, raw, 0, bytes);

                long active = 0;
                int minX = bmp.Width;
                int minY = bmp.Height;
                int maxX = -1;
                int maxY = -1;
                int thresholdSum = threshold * 3;

                for(int y = 0; y < bmp.Height; y++)
                {
                    int row = y * stride;
                    for(int x = 0; x < bmp.Width; x++)
                    {
                        int i = row + x * 4;
                        int b = raw[i + 0];
                        int g = raw[i + 1];
                        int r = raw[i + 2];
                        if((r + g + b) > thresholdSum)
                        {
                            active++;
                            if(x < minX) minX = x;
                            if(y < minY) minY = y;
                            if(x > maxX) maxX = x;
                            if(y > maxY) maxY = y;
                        }
                    }
                }

                OverlayStats stats = new OverlayStats();
                stats.width = bmp.Width;
                stats.height = bmp.Height;
                stats.activePixels = active;
                stats.coverage = (bmp.Width > 0 && bmp.Height > 0) ? (double)active / ((double)bmp.Width * (double)bmp.Height) : 0.0;
                stats.bounds = new PixelBox
                {
                    hasBox = active > 0,
                    minX = active > 0 ? minX : 0,
                    minY = active > 0 ? minY : 0,
                    maxX = active > 0 ? maxX : 0,
                    maxY = active > 0 ? maxY : 0,
                };
                return stats;
            }
            finally
            {
                bmp.UnlockBits(data);
            }
        }
    }

    public static DiffStats ComputeDiff(string previousPath, string currentPath, int threshold)
    {
        using(Bitmap loadedPrev = (Bitmap)Image.FromFile(previousPath))
        using(Bitmap loadedCurr = (Bitmap)Image.FromFile(currentPath))
        using(Bitmap prev = Normalize(loadedPrev))
        using(Bitmap curr = Normalize(loadedCurr))
        {
            if(prev.Width != curr.Width || prev.Height != curr.Height)
                throw new InvalidOperationException("Image dimensions do not match for diff");

            Rectangle rect = new Rectangle(0, 0, prev.Width, prev.Height);
            BitmapData prevData = prev.LockBits(rect, ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
            BitmapData currData = curr.LockBits(rect, ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);

            try
            {
                int stride = prevData.Stride;
                int bytes = stride * prev.Height;
                byte[] rawPrev = new byte[bytes];
                byte[] rawCurr = new byte[bytes];
                System.Runtime.InteropServices.Marshal.Copy(prevData.Scan0, rawPrev, 0, bytes);
                System.Runtime.InteropServices.Marshal.Copy(currData.Scan0, rawCurr, 0, bytes);

                long changed = 0;
                long totalDiff = 0;
                int minX = prev.Width;
                int minY = prev.Height;
                int maxX = -1;
                int maxY = -1;
                int thresholdSum = threshold * 4;

                for(int y = 0; y < prev.Height; y++)
                {
                    int row = y * stride;
                    for(int x = 0; x < prev.Width; x++)
                    {
                        int i = row + x * 4;
                        int diff =
                            Math.Abs(rawPrev[i + 0] - rawCurr[i + 0]) +
                            Math.Abs(rawPrev[i + 1] - rawCurr[i + 1]) +
                            Math.Abs(rawPrev[i + 2] - rawCurr[i + 2]) +
                            Math.Abs(rawPrev[i + 3] - rawCurr[i + 3]);

                        if(diff > thresholdSum)
                        {
                            changed++;
                            totalDiff += diff;
                            if(x < minX) minX = x;
                            if(y < minY) minY = y;
                            if(x > maxX) maxX = x;
                            if(y > maxY) maxY = y;
                        }
                    }
                }

                DiffStats stats = new DiffStats();
                stats.width = prev.Width;
                stats.height = prev.Height;
                stats.changedPixels = changed;
                stats.changeRatio = (prev.Width > 0 && prev.Height > 0) ? (double)changed / ((double)prev.Width * (double)prev.Height) : 0.0;
                stats.meanDiff = changed > 0 ? (double)totalDiff / (double)changed : 0.0;
                stats.bounds = new PixelBox
                {
                    hasBox = changed > 0,
                    minX = changed > 0 ? minX : 0,
                    minY = changed > 0 ? minY : 0,
                    maxX = changed > 0 ? maxX : 0,
                    maxY = changed > 0 ? maxY : 0,
                };
                return stats;
            }
            finally
            {
                prev.UnlockBits(prevData);
                curr.UnlockBits(currData);
            }
        }
    }
}
"@
}

$result = [ordered]@{}

if ($OverlayPath) {
    $result.overlay = [RenderDocImageStats]::ComputeOverlay($OverlayPath, $OverlayThreshold)
}

if ($PreviousPath -and $CurrentPath) {
    $result.diff = [RenderDocImageStats]::ComputeDiff($PreviousPath, $CurrentPath, $DiffThreshold)
}

$result | ConvertTo-Json -Depth 6
