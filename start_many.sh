python -m bcws -L p2d gossip -p "11120" --nd &

for i in 1 2 3 4 5 6
do
    python -m bcws gossip -p "1112$i" -P 127.0.0.1:11120 &
    sleep 1
done