##download data 


wget https://github.com/chenditc/investment_data/releases/latest/download/qlib_bin.tar.gz
mkdir -p /Users/yingwei/Documents/code/finance/qlib_data/cn_data
tar -zxvf qlib_bin.tar.gz -C /Users/yingwei/Documents/code/finance/qlib_data/cn_data --strip-components=1
rm -f qlib_bin.tar.gz
